"""Intelligence pipeline Kafka worker."""

import asyncio
import logging
import uuid
from typing import Any

from mip_database.config import get_settings
from mip_database.models import Event, EventEvidence, EvidenceSpan
from mip_database.repositories import SentimentRepository
from mip_database.session import async_session_factory
from mip_intelligence.engine import generate_signal_for_event, update_narrative
from mip_messaging import KafkaConsumer, KafkaProducer, wrap_payload
from mip_observability import DOCUMENT_THROUGHPUT, setup_logging
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def process_events_message(message: dict[str, Any], producer: KafkaProducer) -> None:
    payload = message.get("payload", message)
    settings = get_settings()
    events_data = payload.get("events", [])
    document_id = payload.get("document_id")

    async with async_session_factory() as session:
        sentiment_score = 0.0
        if document_id:
            sentiment_repo = SentimentRepository(session)
            sentiment_record = await sentiment_repo.get_by_document(uuid.UUID(document_id))
            if sentiment_record:
                scores = sentiment_record.scores or {}
                sentiment_score = float(scores.get("hawkish_dovish", 0.0))

        for evt_data in events_data:
            event_id = uuid.UUID(evt_data["event_id"])
            result = await session.execute(select(Event).where(Event.event_id == event_id))
            event = result.scalar_one_or_none()
            if not event:
                continue

            topic_labels = (
                [event.event_type.split("_")[0]] if "_" in event.event_type else [event.event_type]
            )
            narrative = await update_narrative(
                session, event, topic_labels, sentiment_score=sentiment_score
            )

            ev_result = await session.execute(
                select(EvidenceSpan.evidence_id)
                .join(EventEvidence, EventEvidence.evidence_id == EvidenceSpan.evidence_id)
                .where(EventEvidence.event_id == event_id)
            )
            evidence_ids = [row[0] for row in ev_result.all()]
            if not evidence_ids:
                continue

            signal = await generate_signal_for_event(
                session,
                event,
                narrative,
                evidence_ids,
                sentiment_score=sentiment_score,
            )
            await session.commit()

            signal_msg = wrap_payload(
                {
                    "signal_id": str(signal.signal_id),
                    "signal_type": signal.signal_type,
                    "score": signal.score,
                    "confidence": signal.confidence,
                    "narrative_id": str(narrative.narrative_id),
                    "document_id": document_id,
                    "tenant_id": settings.default_tenant_id,
                },
                event_type="signal.generated",
                producer="intelligence-worker",
                producer_version="0.1.0",
            )
            await producer.publish("signals.generated.v1", signal_msg)

            alert_msg = wrap_payload(
                {
                    "signal_id": str(signal.signal_id),
                    "signal_type": signal.signal_type,
                    "score": signal.score,
                    "confidence": signal.confidence,
                    "narrative_id": str(narrative.narrative_id),
                    "tenant_id": settings.default_tenant_id,
                    "event_type": event.event_type,
                    "topic_labels": topic_labels,
                    "entity_ids": [],
                    "countries": [],
                },
                event_type="alert.candidate",
                producer="intelligence-worker",
                producer_version="0.1.0",
            )
            await producer.publish("alerts.candidate.v1", alert_msg)

    DOCUMENT_THROUGHPUT.labels(service="intelligence-worker", status="success").inc()


async def run_intelligence_worker() -> None:
    setup_logging()
    settings = get_settings()
    consumer = KafkaConsumer(
        settings.kafka_bootstrap_servers,
        group_id="intelligence-worker",
        topics=["events.extracted.v1"],
    )
    producer = KafkaProducer(settings.kafka_bootstrap_servers)
    await consumer.start()
    await producer.start()
    logger.info("Intelligence worker started")

    async def handler(msg: dict[str, Any]) -> None:
        await process_events_message(msg, producer)

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
    asyncio.run(run_intelligence_worker())


if __name__ == "__main__":
    main()
