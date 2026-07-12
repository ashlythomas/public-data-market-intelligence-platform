"""Shared connector runner utilities."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from mip_database.config import get_settings
from mip_database.models import IngestionRun, RawDocument
from mip_database.session import async_session_factory
from mip_database.storage import ObjectStorage
from mip_messaging import KafkaProducer, wrap_payload
from mip_observability import CONNECTOR_LAG, DOCUMENT_THROUGHPUT, setup_logging
from sqlalchemy import select

if TYPE_CHECKING:
    from mip_connector_fed.base import BaseConnector

logger = logging.getLogger(__name__)


async def run_connector(
    connector: "BaseConnector",
    *,
    source_id: str,
    kafka_topic: str,
) -> dict:
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
    final_checkpoint: dict | None = None

    async with async_session_factory() as session:
        checkpoint_result = await session.execute(
            select(IngestionRun.checkpoint)
            .where(
                IngestionRun.source_id == source_id,
                IngestionRun.status == "completed",
                IngestionRun.checkpoint.is_not(None),
            )
            .order_by(IngestionRun.completed_at.desc())
            .limit(1)
        )
        previous_checkpoint = checkpoint_result.scalar_one_or_none()
        run = IngestionRun(run_id=run_id, source_id=source_id, status="running")
        session.add(run)
        await session.commit()

    try:
        async with connector:
            connector.load_checkpoint(previous_checkpoint)
            async for item in connector.discover(previous_checkpoint):
                try:
                    payload = await connector.fetch_with_retry(item)
                    content_hash = connector.content_hash(payload.content)
                    ingestion_id = uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"{source_id}:{payload.external_id or payload.source_url}:{content_hash}",
                    )
                    async with async_session_factory() as session:
                        existing = await session.get(RawDocument, ingestion_id)
                        if existing is not None:
                            DOCUMENT_THROUGHPUT.labels(
                                service=f"{connector.connector_name}-connector",
                                status="duplicate",
                            ).inc()
                            continue

                        extension = "html" if "html" in payload.content_type else "bin"
                        uri, stored_hash = await asyncio.to_thread(
                            storage.store_raw,
                            source_id=source_id,
                            ingestion_id=ingestion_id,
                            content=payload.content,
                            extension=extension,
                            retrieved_at=datetime.now(UTC),
                        )
                        session.add(
                            RawDocument(
                                ingestion_id=ingestion_id,
                                source_id=source_id,
                                external_id=payload.external_id,
                                source_url=payload.source_url,
                                retrieved_at=datetime.now(UTC),
                                published_at=payload.published_at,
                                content_type=payload.content_type,
                                object_store_uri=uri,
                                content_hash=stored_hash,
                                connector_version=connector.connector_version,
                                metadata_=payload.metadata,
                            )
                        )
                        await session.commit()
                        envelope = connector.build_envelope(payload, uri, ingestion_id)
                        envelope["tenant_id"] = settings.default_tenant_id

                    message = wrap_payload(
                        envelope,
                        event_type="raw.document.ingested",
                        producer=f"{connector.connector_name}-connector",
                        producer_version=connector.connector_version,
                    )
                    await producer.publish(kafka_topic, message)
                    items_ingested += 1
                    DOCUMENT_THROUGHPUT.labels(
                        service=f"{connector.connector_name}-connector", status="success"
                    ).inc()
                except Exception as e:
                    logger.exception("Failed to ingest item %s: %s", item.url, e)
                    items_failed += 1
                    DOCUMENT_THROUGHPUT.labels(
                        service=f"{connector.connector_name}-connector", status="failed"
                    ).inc()

            final_checkpoint = await connector.checkpoint()
    finally:
        await producer.stop()

    async with async_session_factory() as session:
        run = await session.get(IngestionRun, run_id)
        if run:
            run.status = "completed" if items_failed == 0 else "partial"
            run.completed_at = datetime.now(UTC)
            run.items_ingested = items_ingested
            run.items_failed = items_failed
            run.checkpoint = final_checkpoint
            await session.commit()

    CONNECTOR_LAG.labels(source_id=source_id).set(0)
    return {"items_ingested": items_ingested, "items_failed": items_failed}
