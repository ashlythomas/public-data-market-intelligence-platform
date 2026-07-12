"""Federal Reserve connector runner."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from mip_connector_fed.connector import FedConnector
from mip_database.config import get_settings
from mip_database.models import IngestionRun, RawDocument
from mip_database.session import async_session_factory
from mip_database.storage import ObjectStorage
from mip_messaging import KafkaProducer, wrap_payload
from mip_observability import CONNECTOR_LAG, DOCUMENT_THROUGHPUT, setup_logging

logger = logging.getLogger(__name__)


async def run_fed_connector() -> dict:
    setup_logging()
    settings = get_settings()
    storage = ObjectStorage(
        endpoint_url=settings.s3_endpoint_url,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        bucket=settings.s3_bucket_raw,
    )
    producer = KafkaProducer(settings.kafka_bootstrap_servers)
    await producer.start()

    run_id = uuid.uuid4()
    items_ingested = 0
    items_failed = 0

    async with async_session_factory() as session:
        run = IngestionRun(run_id=run_id, source_id="fed", status="running")
        session.add(run)
        await session.commit()

    try:
        async with FedConnector() as connector:
            checkpoint = None
            async for item in connector.discover(checkpoint):
                try:
                    payload = await connector.fetch_with_retry(item)
                    ingestion_id = uuid.uuid4()
                    extension = "html" if "html" in payload.content_type else "bin"
                    uri, content_hash = storage.store_raw(
                        source_id="fed",
                        ingestion_id=ingestion_id,
                        content=payload.content,
                        extension=extension,
                        retrieved_at=datetime.now(UTC),
                    )

                    async with async_session_factory() as session:
                        raw_doc = RawDocument(
                            ingestion_id=ingestion_id,
                            source_id="fed",
                            external_id=payload.external_id,
                            source_url=payload.source_url,
                            retrieved_at=datetime.now(UTC),
                            published_at=payload.published_at,
                            content_type=payload.content_type,
                            object_store_uri=uri,
                            content_hash=content_hash,
                            connector_version=connector.connector_version,
                            metadata_=payload.metadata,
                        )
                        session.add(raw_doc)
                        await session.commit()

                    envelope = connector.build_envelope(payload, uri, ingestion_id)
                    message = wrap_payload(
                        envelope,
                        event_type="raw.document.ingested",
                        producer="fed-connector",
                        producer_version=connector.connector_version,
                    )
                    await producer.publish("raw.central-bank.v1", message)
                    items_ingested += 1
                    DOCUMENT_THROUGHPUT.labels(service="fed-connector", status="success").inc()
                except Exception as e:
                    logger.exception("Failed to ingest item %s: %s", item.url, e)
                    items_failed += 1
                    DOCUMENT_THROUGHPUT.labels(service="fed-connector", status="failed").inc()

            final_checkpoint = await connector.checkpoint()
    finally:
        await producer.stop()

    async with async_session_factory() as session:
        run = await session.get(IngestionRun, run_id)
        if run:
            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            run.items_ingested = items_ingested
            run.items_failed = items_failed
            run.checkpoint = final_checkpoint
            await session.commit()

    CONNECTOR_LAG.labels(source_id="fed").set(0)
    return {"items_ingested": items_ingested, "items_failed": items_failed}


def main() -> None:
    result = asyncio.run(run_fed_connector())
    print(f"Fed connector completed: {result}")


if __name__ == "__main__":
    main()
