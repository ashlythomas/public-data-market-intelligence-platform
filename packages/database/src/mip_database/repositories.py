import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mip_database.models import (
    AlertRule,
    CanonicalDocument,
    Entity,
    Event,
    EvidenceSpan,
    Narrative,
    RawDocument,
    Signal,
    Source,
)


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
        count_result = await self.session.execute(query)
        total = len(count_result.scalars().all())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def create(self, doc: CanonicalDocument) -> CanonicalDocument:
        self.session.add(doc)
        await self.session.flush()
        return doc

    async def get_by_content_hash(self, content_hash: str) -> CanonicalDocument | None:
        result = await self.session.execute(
            select(CanonicalDocument).where(CanonicalDocument.content_hash == content_hash)
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
        count_result = await self.session.execute(query)
        total = len(count_result.scalars().all())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def create(self, event: Event) -> Event:
        self.session.add(event)
        await self.session.flush()
        return event


class EntityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, entity_id: uuid.UUID) -> Entity | None:
        result = await self.session.execute(select(Entity).where(Entity.entity_id == entity_id))
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
        count_result = await self.session.execute(query)
        total = len(count_result.scalars().all())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total


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
        count_result = await self.session.execute(query)
        total = len(count_result.scalars().all())
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
        count_result = await self.session.execute(query)
        total = len(count_result.scalars().all())
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

    async def create(self, evidence: EvidenceSpan) -> EvidenceSpan:
        self.session.add(evidence)
        await self.session.flush()
        return evidence


class SourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, source_id: str) -> Source | None:
        result = await self.session.execute(select(Source).where(Source.source_id == source_id))
        return result.scalar_one_or_none()

    async def create(self, source: Source) -> Source:
        self.session.add(source)
        await self.session.flush()
        return source


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
