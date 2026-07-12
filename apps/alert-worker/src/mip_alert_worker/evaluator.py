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
    deliveries: list[dict[str, Any]] = []

    async with async_session_factory() as session:
        result = await session.execute(select(AlertRule).where(AlertRule.active.is_(True)))
        rules = list(result.scalars().all())

        for rule in rules:
            if rule.signal_types and signal_type not in rule.signal_types:
                continue
            if score < rule.minimum_score:
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
    async with async_session_factory() as session:
        session.add(
            AlertDelivery(
                delivery_id=uuid.uuid4(),
                alert_id=alert_id,
                channel=channel,
                status=status,
                delivered_at=datetime.now(UTC) if status == "delivered" else None,
                payload=payload,
                error_message=error,
            )
        )
        await session.commit()
