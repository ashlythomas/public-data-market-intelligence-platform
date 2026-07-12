"""Alert worker with Kafka consumer."""

import asyncio
import logging
import uuid
from typing import Any

from mip_alert_worker.evaluator import evaluate_alert_candidate, record_delivery
from mip_alert_worker.worker import deliver_email, deliver_webhook
from mip_database.config import get_settings
from mip_messaging import KafkaConsumer
from mip_observability import setup_logging

logger = logging.getLogger(__name__)


async def process_alert_message(message: dict[str, Any]) -> None:
    payload = message.get("payload", message)
    deliveries = await evaluate_alert_candidate(payload)

    for task in deliveries:
        channel = task["channel"]
        delivery_payload = task["delivery_payload"]
        alert_id = uuid.UUID(task["alert_id"])
        success = False
        error = None
        try:
            if channel == "webhook":
                success = await deliver_webhook(
                    task.get("webhook_url", "http://localhost:9999/webhook"),
                    delivery_payload,
                )
            elif channel == "email":
                success = await deliver_email("analyst@example.com", delivery_payload)
            else:
                success = True
        except Exception as e:
            error = str(e)
            logger.exception("Delivery failed")

        await record_delivery(
            alert_id,
            channel,
            "delivered" if success else "failed",
            delivery_payload,
            error,
        )


async def run_alert_worker() -> None:
    setup_logging()
    settings = get_settings()
    consumer = KafkaConsumer(
        settings.kafka_bootstrap_servers,
        group_id="alert-worker",
        topics=["alerts.candidate.v1"],
    )
    await consumer.start()
    logger.info("Alert worker started")

    async def handler(msg: dict[str, Any]) -> None:
        await process_alert_message(msg)

    try:
        async for _ in consumer.consume(handler):
            pass
    finally:
        await consumer.stop()


def main() -> None:
    asyncio.run(run_alert_worker())


if __name__ == "__main__":
    main()
