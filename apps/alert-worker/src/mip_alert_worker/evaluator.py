"""Alert rule evaluation and delivery."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from mip_database.models import AlertDelivery, AlertRule
from mip_database.session import async_session_factory
from mip_observability import setup_logging
from sqlalchemy import select

logger = logging.getLogger(__name__)

# In-memory cooldown tracker (use Redis in production)
_cooldowns: dict[str, datetime] = {}


async def evaluate_alert_candidate(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Match signal against active alert rules and return delivery tasks."""
    setup_logging()
    signal_type = payload.get("signal_type")
    score = payload.get("score", 0.0)
    confidence = payload.get("confidence", 0.0)
    tenant_id = uuid.UUID(payload["tenant_id"])
    deliveries: list[dict[str, Any]] = []

    async with async_session_factory() as session:
        result = await session.execute(
            select(AlertRule).where(
                AlertRule.active.is_(True),
                AlertRule.tenant_id == tenant_id,
            )
        )
        rules = list(result.scalars().all())

        for rule in rules:
            if rule.signal_types and signal_type not in rule.signal_types:
                continue
            if score < rule.minimum_score:
                continue
            if confidence < rule.minimum_confidence:
                continue
            if rule.entity_ids and not {str(value) for value in rule.entity_ids} & {
                str(value) for value in payload.get("entity_ids", [])
            }:
                continue
            if rule.topic_labels and not set(rule.topic_labels) & set(
                payload.get("topic_labels", [])
            ):
                continue
            if rule.event_types and payload.get("event_type") not in rule.event_types:
                continue
            if rule.countries and not set(rule.countries) & set(payload.get("countries", [])):
                continue

            cooldown_key = f"{rule.alert_id}:{signal_type}"
            last_sent = _cooldowns.get(cooldown_key)
            if last_sent and datetime.now(UTC) - last_sent < timedelta(
                seconds=rule.cooldown_period_seconds
            ):
                continue

            for channel in rule.delivery_channels:
                deliveries.append(
                    {
                        "alert_id": str(rule.alert_id),
                        "channel": channel,
                        "delivery_payload": {
                            "subject": f"Signal alert: {signal_type}",
                            "signal_type": signal_type,
                            "score": score,
                            "signal_id": payload.get("signal_id"),
                            "evidence": payload,
                        },
                    }
                )
            _cooldowns[cooldown_key] = datetime.now(UTC)

    return deliveries


async def record_delivery(
    alert_id: uuid.UUID,
    channel: str,
    status: str,
    payload: dict[str, Any],
    error: str | None = None,
) -> None:
    signal_id = str(payload.get("signal_id", "unknown"))
    delivery_id = uuid.uuid5(alert_id, f"{signal_id}:{channel}")
    async with async_session_factory() as session:
        delivery = await session.get(AlertDelivery, delivery_id)
        if delivery is None:
            delivery = AlertDelivery(
                delivery_id=delivery_id,
                alert_id=alert_id,
                channel=channel,
                payload=payload,
            )
            session.add(delivery)
        delivery.status = status
        delivery.delivered_at = datetime.now(UTC) if status == "delivered" else None
        delivery.error_message = error
        await session.commit()


async def delivery_was_successful(
    alert_id: uuid.UUID,
    channel: str,
    signal_id: str,
) -> bool:
    delivery_id = uuid.uuid5(alert_id, f"{signal_id}:{channel}")
    async with async_session_factory() as session:
        delivery = await session.get(AlertDelivery, delivery_id)
        return delivery is not None and delivery.status == "delivered"
