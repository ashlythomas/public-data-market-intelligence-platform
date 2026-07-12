"""Kafka worker: consume raw documents, normalize, deduplicate, index, publish."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from mip_database.config import get_settings
from mip_database.models import CanonicalDocument
from mip_database.repositories import DocumentRepository
from mip_database.session import async_session_factory
from mip_database.storage import ObjectStorage
from mip_messaging import KafkaConsumer, KafkaProducer, wrap_payload
from mip_normalizer.dedup import near_duplicate_check, simhash
from mip_normalizer.parser import normalize_document
from mip_observability import DLQ_COUNT, DOCUMENT_THROUGHPUT, PROCESSING_LATENCY, setup_logging

logger = logging.getLogger(__name__)

RAW_TOPICS = [
    "raw.news.v1",
    "raw.filings.v1",
    "raw.central-bank.v1",
    "raw.economic-data.v1",
    "raw.energy.v1",
    "raw.weather.v1",
]


class OpenSearchIndexer:
    """Sync OpenSearch indexer for pipeline worker."""

    def __init__(self, url: str) -> None:
        from opensearchpy import OpenSearch

        self.client = OpenSearch(hosts=[url], use_ssl=False, verify_certs=False)
        self.index = "documents-v1"

    def ensure_index(self) -> None:
        if not self.client.indices.exists(index=self.index):
            self.client.indices.create(
                index=self.index,
                body={
                    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
                    "mappings": {
                        "properties": {
                            "document_id": {"type": "keyword"},
                            "source_id": {"type": "keyword"},
                            "title": {"type": "text"},
                            "body": {"type": "text"},
                            "summary": {"type": "text"},
                            "language": {"type": "keyword"},
                            "published_at": {"type": "date"},
                            "topic_labels": {"type": "keyword"},
                            "content_hash": {"type": "keyword"},
                        }
                    },
                },
            )

    def index_document(self, doc: dict[str, Any]) -> None:
        self.client.index(index=self.index, id=doc["document_id"], body=doc, refresh=True)


class NormalizerResources:
    """Reusable clients for the normalizer worker."""

    def __init__(self) -> None:
        settings = get_settings()
        self.storage = ObjectStorage(
            endpoint_url=settings.s3_endpoint_url,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            bucket=settings.s3_bucket_raw,
        )
        self.indexer = OpenSearchIndexer(settings.opensearch_url)


async def process_raw_message(
    message: dict[str, Any],
    producer: KafkaProducer,
    resources: NormalizerResources,
) -> None:
    import time

    start = time.monotonic()
    payload = message.get("payload", message)

    object_uri = payload["object_store_uri"]
    key = resources.storage.uri_to_key(object_uri)
    content = await asyncio.to_thread(resources.storage.get_object, key)

    normalized = normalize_document(raw_envelope=payload, content=content)
    if not normalized:
        DLQ_COUNT.labels(topic="dlq.normalization.v1").inc()
        await producer.publish_dlq("dlq.normalization.v1", message, "empty_or_low_content")
        return

    document_id = uuid.UUID(normalized["document_id"])

    async with async_session_factory() as session:
        doc_repo = DocumentRepository(session)

        existing_by_id = await doc_repo.get_by_ingestion_id(document_id)
        if existing_by_id is None:
            existing = await doc_repo.get_by_content_hash(normalized["content_hash"])
            if existing:
                DOCUMENT_THROUGHPUT.labels(service="normalizer", status="duplicate").inc()
                return

            recent_docs = await doc_repo.get_recent_for_dedup(limit=100)
            fingerprints = [
                (str(d.document_id), simhash((d.title or "") + " " + d.body[:500]))
                for d in recent_docs
            ]
            near = near_duplicate_check(
                (normalized.get("title") or "") + " " + normalized["body"],
                fingerprints,
                threshold=8,
            )

            published_at = None
            if normalized.get("published_at"):
                published_at = datetime.fromisoformat(normalized["published_at"])

            doc = CanonicalDocument(
                document_id=document_id,
                source_id=normalized["source_id"],
                external_id=normalized.get("external_id"),
                canonical_url=normalized["canonical_url"],
                title=normalized.get("title"),
                body=normalized["body"],
                summary=normalized.get("summary"),
                language=normalized.get("language", "en"),
                published_at=published_at,
                retrieved_at=datetime.fromisoformat(normalized["retrieved_at"]),
                document_type=normalized.get("document_type", "article"),
                country_codes=normalized.get("country_codes", []),
                topic_labels=normalized.get("topic_labels", []),
                content_hash=normalized["content_hash"],
                parser_version=normalized["parser_version"],
                source_record_id=normalized["source_record_id"],
                is_canonical=not near.is_duplicate,
            )
            await doc_repo.create(doc)
            await session.commit()

    await asyncio.to_thread(resources.indexer.index_document, normalized)

    correlation_id = message.get("correlation_id")
    norm_msg = wrap_payload(
        normalized,
        event_type="document.normalized",
        producer="normalizer",
        producer_version="0.1.0",
        correlation_id=correlation_id,
    )
    await producer.publish("documents.normalized.v1", norm_msg)

    enrich_msg = wrap_payload(
        {"document_id": normalized["document_id"], **normalized},
        event_type="document.enrichment_requested",
        producer="normalizer",
        producer_version="0.1.0",
        correlation_id=correlation_id,
    )
    await producer.publish("documents.enrichment-requested.v1", enrich_msg)

    DOCUMENT_THROUGHPUT.labels(service="normalizer", status="success").inc()
    PROCESSING_LATENCY.labels(service="normalizer", stage="normalize").observe(
        time.monotonic() - start
    )


async def run_normalizer_worker() -> None:
    setup_logging()
    settings = get_settings()
    resources = NormalizerResources()
    await asyncio.to_thread(resources.indexer.ensure_index)

    consumer = KafkaConsumer(
        settings.kafka_bootstrap_servers,
        group_id="normalizer-worker",
        topics=RAW_TOPICS,
    )
    producer = KafkaProducer(settings.kafka_bootstrap_servers)
    await consumer.start()
    await producer.start()
    logger.info("Normalizer worker started", extra={"topics": RAW_TOPICS})

    async def handler(msg: dict[str, Any]) -> None:
        await process_raw_message(msg, producer, resources)

    try:
        async for _ in consumer.consume(
            handler,
            dlq_producer=producer,
            dlq_topic="dlq.normalization.v1",
        ):
            pass
    finally:
        await consumer.stop()
        await producer.stop()


def main() -> None:
    asyncio.run(run_normalizer_worker())


if __name__ == "__main__":
    main()
