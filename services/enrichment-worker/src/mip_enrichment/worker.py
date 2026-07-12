"""Enrichment Kafka worker."""

import asyncio
import logging
import uuid
from typing import Any

from mip_database.config import get_settings
from mip_database.models import (
    Entity,
    EntityMention,
    Event,
    EventEvidence,
    EvidenceSpan,
)
from mip_database.repositories import DocumentRepository
from mip_database.session import async_session_factory
from mip_enrichment.extractors import (
    classify_topics,
    extract_entities,
    extract_events,
    score_sentiment,
)
from mip_messaging import KafkaConsumer, KafkaProducer, wrap_payload
from mip_model_client import ModelGatewayClient
from mip_observability import DOCUMENT_THROUGHPUT, setup_logging

logger = logging.getLogger(__name__)


async def process_enrichment_message(message: dict[str, Any], producer: KafkaProducer) -> None:
    payload = message.get("payload", message)
    document_id = uuid.UUID(payload["document_id"])
    body = payload.get("body", "")
    source_url = payload.get("canonical_url", "")

    settings = get_settings()
    gateway = ModelGatewayClient(settings.model_gateway_url)
    embed_response = await gateway.embed([body[:2000]])
    await gateway.close()

    entities_data = extract_entities(body, document_id)
    topics = classify_topics(body)
    events_data = extract_events(body, document_id, source_url)
    sentiment = score_sentiment(body)

    async with async_session_factory() as session:
        doc_repo = DocumentRepository(session)
        doc = await doc_repo.get_by_id(document_id)
        if doc:
            doc.topic_labels = [t["label"] for t in topics]
            await session.commit()

        for ent in entities_data:
            entity = Entity(
                entity_id=uuid.uuid4(),
                canonical_name=ent["text"],
                entity_type=ent["entity_type"],
            )
            session.add(entity)
            session.add(
                EntityMention(
                    mention_id=uuid.UUID(ent["mention_id"]),
                    document_id=document_id,
                    text=ent["text"],
                    entity_type=ent["entity_type"],
                    start_offset=ent["start_offset"],
                    end_offset=ent["end_offset"],
                    canonical_entity_id=entity.entity_id,
                    extraction_confidence=ent["extraction_confidence"],
                    linking_confidence=0.8,
                    model_version=ent["model_version"],
                )
            )

        for evt in events_data:
            evidence = evt["evidence"]
            event = Event(
                event_id=uuid.UUID(evt["event_id"]),
                document_id=document_id,
                event_type=evt["event_type"],
                action=evt["action"],
                confidence=evt["confidence"],
                extraction_model_version=evt["extraction_model_version"],
            )
            session.add(event)
            session.add(
                EvidenceSpan(
                    evidence_id=uuid.UUID(evidence["evidence_id"]),
                    document_id=document_id,
                    start_offset=evidence["start_offset"],
                    end_offset=evidence["end_offset"],
                    text=evidence["text"],
                    source_url=evidence["source_url"],
                    model_version=evidence["model_version"],
                    confidence=evidence["confidence"],
                )
            )
            session.add(
                EventEvidence(
                    event_id=uuid.UUID(evt["event_id"]),
                    evidence_id=uuid.UUID(evidence["evidence_id"]),
                )
            )
        await session.commit()

    entity_msg = wrap_payload(
        {"document_id": str(document_id), "entities": entities_data},
        event_type="entities.extracted",
        producer="enrichment-worker",
        producer_version="0.1.0",
    )
    await producer.publish("entities.extracted.v1", entity_msg)

    if events_data:
        event_msg = wrap_payload(
            {"document_id": str(document_id), "events": events_data},
            event_type="events.extracted",
            producer="enrichment-worker",
            producer_version="0.1.0",
        )
        await producer.publish("events.extracted.v1", event_msg)

    embed_msg = wrap_payload(
        {
            "document_id": str(document_id),
            "embedding": embed_response.embeddings[0],
            "model_version": embed_response.model_version,
            "sentiment": sentiment,
        },
        event_type="embeddings.generated",
        producer="enrichment-worker",
        producer_version="0.1.0",
    )
    await producer.publish("embeddings.generated.v1", embed_msg)

    DOCUMENT_THROUGHPUT.labels(service="enrichment-worker", status="success").inc()


async def run_enrichment_worker() -> None:
    setup_logging()
    settings = get_settings()
    consumer = KafkaConsumer(
        settings.kafka_bootstrap_servers,
        group_id="enrichment-worker",
        topics=["documents.enrichment-requested.v1"],
    )
    producer = KafkaProducer(settings.kafka_bootstrap_servers)
    await consumer.start()
    await producer.start()
    logger.info("Enrichment worker started")

    async def handler(msg: dict[str, Any]) -> None:
        await process_enrichment_message(msg, producer)

    try:
        async for _ in consumer.consume(
            handler, dlq_producer=producer, dlq_topic="dlq.enrichment.v1"
        ):
            pass
    finally:
        await consumer.stop()
        await producer.stop()


def main() -> None:
    asyncio.run(run_enrichment_worker())


if __name__ == "__main__":
    main()
