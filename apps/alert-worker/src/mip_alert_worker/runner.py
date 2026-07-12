"""Alert worker with Kafka consumer."""

import asyncio
import logging
import uuid
from typing import Any

from mip_alert_worker.evaluator import (
    delivery_was_successful,
    evaluate_alert_candidate,
    record_delivery,
)
from mip_alert_worker.worker import deliver_email, deliver_webhook
from mip_database.config import get_settings
from mip_messaging import KafkaConsumer, KafkaProducer
from mip_observability import setup_logging

logger = logging.getLogger(__name__)
MAX_DELIVERY_RETRIES = 3


async def _deliver_with_retries(
    channel: str,
    task: dict[str, Any],
    delivery_payload: dict[str, Any],
) -> tuple[bool, str | None]:
    last_error: str | None = None
    for attempt in range(1, MAX_DELIVERY_RETRIES + 1):
        try:
            if channel == "webhook":
                webhook_url = task.get("webhook_url")
                if not webhook_url:
                    return False, "missing webhook_url in alert delivery config"
                success = await deliver_webhook(
                    webhook_url,
                    delivery_payload,
                )
            elif channel == "email":
                email_to = task.get("email")
                if not email_to:
                    return False, "missing email recipient in alert delivery config"
                success = await deliver_email(email_to, delivery_payload)
            else:
                success = True

            if success:
                return True, None
            last_error = f"{channel} delivery returned unsuccessful status"
        except Exception as exc:  # pragma: no cover - defensive retry path
            last_error = str(exc)
            logger.exception("Delivery failed", extra={"channel": channel, "attempt": attempt})

        if attempt < MAX_DELIVERY_RETRIES:
            await asyncio.sleep(attempt)

    return False, last_error


async def process_alert_message(message: dict[str, Any]) -> None:
    payload = message.get("payload", message)
    deliveries = await evaluate_alert_candidate(payload)

    for task in deliveries:
        channel = task["channel"]
        delivery_payload = task["delivery_payload"]
        alert_id = uuid.UUID(task["alert_id"])
        signal_id = str(delivery_payload.get("signal_id", "unknown"))
        if await delivery_was_successful(alert_id, channel, signal_id):
            continue
        success, error = await _deliver_with_retries(channel, task, delivery_payload)

        await record_delivery(
            alert_id,
            channel,
            "delivered" if success else "failed",
            delivery_payload,
            error,
        )
        if not success:
            raise RuntimeError(error or "alert delivery failed")


async def run_alert_worker() -> None:
    setup_logging()
    settings = get_settings()
    consumer = KafkaConsumer(
        settings.kafka_bootstrap_servers,
        group_id="alert-worker",
        topics=["alerts.candidate.v1"],
    )
    producer = KafkaProducer(settings.kafka_bootstrap_servers)
    await consumer.start()
    await producer.start()
    logger.info("Alert worker started")

    async def handler(msg: dict[str, Any]) -> None:
        await process_alert_message(msg)

    try:
        async for _ in consumer.consume(
            handler,
            dlq_producer=producer,
            dlq_topic="dlq.persistence.v1",
        ):
            pass
    finally:
        await consumer.stop()
        await producer.stop()


def main() -> None:
    asyncio.run(run_alert_worker())


if __name__ == "__main__":
    main()
