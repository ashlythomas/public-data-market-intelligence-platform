"""Alert delivery worker."""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
from mip_database.models import AlertDelivery
from mip_database.session import async_session_factory
from mip_observability import setup_logging

logger = logging.getLogger(__name__)


async def deliver_webhook(url: str, payload: dict[str, Any]) -> bool:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)
        return response.is_success


async def deliver_email(to: str, payload: dict[str, Any]) -> bool:
    logger.info("Email delivery (mock): to=%s subject=%s", to, payload.get("subject"))
    return True


async def process_alert_candidate(message: dict[str, Any]) -> None:
    setup_logging()
    payload = message.get("payload", message)
    alert_id = payload.get("alert_id")
    channel = payload.get("channel", "email")
    delivery_payload = payload.get("delivery_payload", {})

    delivery = AlertDelivery(
        delivery_id=uuid4(),
        alert_id=alert_id,
        channel=channel,
        status="pending",
        payload=delivery_payload,
    )

    success = False
    error_message = None
    try:
        if channel == "webhook":
            success = await deliver_webhook(payload.get("webhook_url", ""), delivery_payload)
        elif channel == "email":
            success = await deliver_email(payload.get("email", ""), delivery_payload)
        else:
            success = True
    except Exception as e:
        error_message = str(e)
        logger.exception("Alert delivery failed")

    delivery.status = "delivered" if success else "failed"
    delivery.delivered_at = datetime.now(UTC) if success else None
    delivery.error_message = error_message

    async with async_session_factory() as session:
        session.add(delivery)
        await session.commit()
