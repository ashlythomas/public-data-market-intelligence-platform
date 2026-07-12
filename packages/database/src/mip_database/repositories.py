import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mip_database.models import (
    AlertRule,
    CanonicalDocument,
    DocumentEmbedding,
    DocumentSentiment,
    Entity,
    EntityAlias,
    Event,
    EvidenceSpan,
    Narrative,
    RawDocument,
    Signal,
    Source,
)
from mip_database.pagination import count_query


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, document_id: uuid.UUID) -> CanonicalDocument | None:
        result = await self.session.execute(
            select(CanonicalDocument).where(CanonicalDocument.document_id == document_id)
        )
        return result.scalar_one_or_none()

    async def list_documents(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        source_id: str | None = None,
    ) -> tuple[list[CanonicalDocument], int]:
        query = select(CanonicalDocument).where(CanonicalDocument.is_canonical.is_(True))
        if source_id:
            query = query.where(CanonicalDocument.source_id == source_id)
        total = await count_query(self.session, query)
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def get_recent_for_dedup(self, limit: int = 100) -> list[CanonicalDocument]:
        result = await self.session.execute(
            select(CanonicalDocument)
            .where(CanonicalDocument.is_canonical.is_(True))
            .order_by(CanonicalDocument.retrieved_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, doc: CanonicalDocument) -> CanonicalDocument:
        self.session.add(doc)
        await self.session.flush()
        return doc

    async def get_by_content_hash(self, content_hash: str) -> CanonicalDocument | None:
        result = await self.session.execute(
            select(CanonicalDocument).where(CanonicalDocument.content_hash == content_hash)
        )
        return result.scalar_one_or_none()

    async def get_by_ingestion_id(self, ingestion_id: uuid.UUID) -> CanonicalDocument | None:
        """Lookup by deterministic document_id derived from ingestion_id."""
        result = await self.session.execute(
            select(CanonicalDocument).where(CanonicalDocument.document_id == ingestion_id)
        )
        return result.scalar_one_or_none()


class RawDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_hash(self, content_hash: str) -> RawDocument | None:
        result = await self.session.execute(
            select(RawDocument).where(RawDocument.content_hash == content_hash)
        )
        return result.scalar_one_or_none()

    async def create(self, doc: RawDocument) -> RawDocument:
        self.session.add(doc)
        await self.session.flush()
        return doc


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, event_id: uuid.UUID) -> Event | None:
        result = await self.session.execute(select(Event).where(Event.event_id == event_id))
        return result.scalar_one_or_none()

    async def list_events(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        event_type: str | None = None,
    ) -> tuple[list[Event], int]:
        query = select(Event)
        if event_type:
            query = query.where(Event.event_type == event_type)
        total = await count_query(self.session, query)
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def create(self, event: Event) -> Event:
        self.session.add(event)
        await self.session.flush()
        return event

    async def find_similar(
        self,
        event_type: str,
        *,
        within_hours: int = 72,
        limit: int = 20,
    ) -> list[Event]:
        from datetime import UTC, datetime, timedelta

        cutoff = datetime.now(UTC) - timedelta(hours=within_hours)
        result = await self.session.execute(
            select(Event)
            .where(Event.event_type == event_type)
            .where((Event.event_time >= cutoff) | (Event.event_time.is_(None)))
            .order_by(Event.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class EntityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, entity_id: uuid.UUID) -> Entity | None:
        result = await self.session.execute(select(Entity).where(Entity.entity_id == entity_id))
        return result.scalar_one_or_none()

    async def find_by_alias(self, name: str, entity_type: str | None = None) -> Entity | None:
        normalized = name.strip().lower()
        query = (
            select(Entity)
            .join(EntityAlias, EntityAlias.entity_id == Entity.entity_id)
            .where(func.lower(EntityAlias.alias) == normalized)
        )
        if entity_type:
            query = query.where(Entity.entity_type == entity_type)
        result = await self.session.execute(query.limit(1))
        return result.scalar_one_or_none()

    async def find_by_canonical_name(self, name: str, entity_type: str) -> Entity | None:
        result = await self.session.execute(
            select(Entity).where(
                func.lower(Entity.canonical_name) == name.strip().lower(),
                Entity.entity_type == entity_type,
            )
        )
        return result.scalar_one_or_none()

    async def list_entities(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        entity_type: str | None = None,
    ) -> tuple[list[Entity], int]:
        query = select(Entity)
        if entity_type:
            query = query.where(Entity.entity_type == entity_type)
        total = await count_query(self.session, query)
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def create(self, entity: Entity, aliases: list[str] | None = None) -> Entity:
        self.session.add(entity)
        await self.session.flush()
        for alias in aliases or [entity.canonical_name]:
            self.session.add(
                EntityAlias(entity_id=entity.entity_id, alias=alias),
            )
        await self.session.flush()
        return entity


class NarrativeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, narrative_id: uuid.UUID) -> Narrative | None:
        result = await self.session.execute(
            select(Narrative).where(Narrative.narrative_id == narrative_id)
        )
        return result.scalar_one_or_none()

    async def list_narratives(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Narrative], int]:
        query = select(Narrative)
        total = await count_query(self.session, query)
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total


class SignalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, signal_id: uuid.UUID) -> Signal | None:
        result = await self.session.execute(select(Signal).where(Signal.signal_id == signal_id))
        return result.scalar_one_or_none()

    async def list_signals(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        signal_type: str | None = None,
    ) -> tuple[list[Signal], int]:
        query = select(Signal)
        if signal_type:
            query = query.where(Signal.signal_type == signal_type)
        total = await count_query(self.session, query)
        query = query.order_by(Signal.generated_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total


class EvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_document(self, document_id: uuid.UUID) -> list[EvidenceSpan]:
        result = await self.session.execute(
            select(EvidenceSpan).where(EvidenceSpan.document_id == document_id)
        )
        return list(result.scalars().all())


class SourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, source_id: str) -> Source | None:
        result = await self.session.execute(select(Source).where(Source.source_id == source_id))
        return result.scalar_one_or_none()

    async def get_by_ids(self, source_ids: list[str]) -> dict[str, Source]:
        if not source_ids:
            return {}
        result = await self.session.execute(select(Source).where(Source.source_id.in_(source_ids)))
        return {s.source_id: s for s in result.scalars().all()}

    async def create(self, source: Source) -> Source:
        self.session.add(source)
        await self.session.flush()
        return source


class EmbeddingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        document_id: uuid.UUID,
        embedding: list[float],
        model_version: str,
    ) -> DocumentEmbedding:
        existing = await self.session.get(DocumentEmbedding, document_id)
        if existing:
            existing.embedding = embedding
            existing.model_version = model_version
            await self.session.flush()
            return existing
        record = DocumentEmbedding(
            document_id=document_id,
            embedding=embedding,
            model_version=model_version,
        )
        self.session.add(record)
        await self.session.flush()
        return record


class SentimentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        document_id: uuid.UUID,
        scores: dict,
        model_version: str,
    ) -> DocumentSentiment:
        existing = await self.session.get(DocumentSentiment, document_id)
        if existing:
            existing.scores = scores
            existing.model_version = model_version
            await self.session.flush()
            return existing
        record = DocumentSentiment(
            document_id=document_id,
            scores=scores,
            model_version=model_version,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_by_document(self, document_id: uuid.UUID) -> DocumentSentiment | None:
        return await self.session.get(DocumentSentiment, document_id)


class AlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, alert_id: uuid.UUID) -> AlertRule | None:
        result = await self.session.execute(select(AlertRule).where(AlertRule.alert_id == alert_id))
        return result.scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: uuid.UUID) -> list[AlertRule]:
        result = await self.session.execute(
            select(AlertRule).where(AlertRule.tenant_id == tenant_id)
        )
        return list(result.scalars().all())

    async def create(self, alert: AlertRule) -> AlertRule:
        self.session.add(alert)
        await self.session.flush()
        return alert

    async def update(self, alert: AlertRule) -> AlertRule:
        await self.session.flush()
        return alert

    async def delete(self, alert: AlertRule) -> None:
        await self.session.delete(alert)
