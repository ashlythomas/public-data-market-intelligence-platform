import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from mip_schemas.messaging import KafkaMessage
from pydantic import BaseModel

logger = logging.getLogger(__name__)

RAW_TOPICS = [
    "raw.news.v1",
    "raw.filings.v1",
    "raw.central-bank.v1",
    "raw.economic-data.v1",
    "raw.energy.v1",
    "raw.weather.v1",
]

PROCESSING_TOPICS = [
    "documents.normalized.v1",
    "documents.deduplicated.v1",
    "documents.enrichment-requested.v1",
    "entities.extracted.v1",
    "entities.linked.v1",
    "topics.classified.v1",
    "events.extracted.v1",
    "sentiment.scored.v1",
    "embeddings.generated.v1",
    "events.clustered.v1",
    "narratives.updated.v1",
    "signals.generated.v1",
    "alerts.candidate.v1",
]

DLQ_TOPICS = [
    "dlq.connector.v1",
    "dlq.normalization.v1",
    "dlq.enrichment.v1",
    "dlq.persistence.v1",
]


class KafkaProducer:
    def __init__(self, bootstrap_servers: str) -> None:
        self.bootstrap_servers = bootstrap_servers
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            acks="all",
            retry_backoff_ms=500,
        )
        await self._producer.start()
        logger.info("Kafka producer started", extra={"bootstrap_servers": self.bootstrap_servers})

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()

    async def publish(self, topic: str, message: KafkaMessage | dict[str, Any]) -> None:
        if not self._producer:
            raise RuntimeError("Producer not started")
        if isinstance(message, KafkaMessage):
            payload = message.model_dump(mode="json")
        else:
            payload = message
        await self._producer.send_and_wait(topic, payload)
        logger.info(
            "Published message",
            extra={"topic": topic, "message_id": str(payload.get("message_id", ""))},
        )

    async def publish_dlq(
        self, dlq_topic: str, original_message: dict[str, Any], error: str
    ) -> None:
        dlq_payload = {
            "original_message": original_message,
            "error": error,
            "dlq_topic": dlq_topic,
        }
        await self.publish(dlq_topic, dlq_payload)


class KafkaConsumer:
    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str,
        topics: list[str],
    ) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.topics = topics
        self._consumer: AIOKafkaConsumer | None = None

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            *self.topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            enable_auto_commit=False,
        )
        await self._consumer.start()
        logger.info(
            "Kafka consumer started",
            extra={"group_id": self.group_id, "topics": self.topics},
        )

    async def stop(self) -> None:
        if self._consumer:
            await self._consumer.stop()

    async def consume(
        self,
        handler: Callable[[dict[str, Any]], Any],
        *,
        dlq_producer: KafkaProducer | None = None,
        dlq_topic: str | None = None,
    ) -> AsyncIterator[None]:
        if not self._consumer:
            raise RuntimeError("Consumer not started")
        async for msg in self._consumer:
            try:
                await handler(msg.value)
                await self._consumer.commit()
            except Exception as e:
                logger.exception("Message processing failed", extra={"error": str(e)})
                if dlq_producer and dlq_topic:
                    await dlq_producer.publish_dlq(dlq_topic, msg.value, str(e))
                await self._consumer.commit()
            yield


def wrap_payload(
    payload: BaseModel | dict[str, Any],
    *,
    event_type: str,
    producer: str,
    producer_version: str,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    if isinstance(payload, BaseModel):
        payload_dict = payload.model_dump(mode="json")
    else:
        payload_dict = payload
    message = KafkaMessage(
        event_type=event_type,
        producer=producer,
        producer_version=producer_version,
        payload=payload_dict,
    )
    if correlation_id:
        message.correlation_id = correlation_id  # type: ignore[assignment]
    return message.model_dump(mode="json")
