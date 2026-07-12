#!/usr/bin/env python3
"""Seed database with sample data demonstrating end-to-end flow."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from mip_api.search import SearchService
from mip_api.signals import calculate_signal
from mip_database.models import (
    CanonicalDocument,
    Entity,
    Event,
    EventEvidence,
    EvidenceSpan,
    Narrative,
    NarrativeEvent,
    Signal,
    SignalEvidence,
    Source,
    Tenant,
    User,
)
from mip_database.session import async_session_factory
from mip_test_fixtures import FED_PRESS_RELEASE_HTML, SAMPLE_SOURCES


async def seed() -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    document_id = uuid.UUID("00000000-0000-0000-0000-000000000010")
    entity_id = uuid.UUID("00000000-0000-0000-0000-000000000020")
    event_id = uuid.UUID("00000000-0000-0000-0000-000000000030")
    evidence_id = uuid.UUID("00000000-0000-0000-0000-000000000040")
    narrative_id = uuid.UUID("00000000-0000-0000-0000-000000000050")
    signal_id = uuid.UUID("00000000-0000-0000-0000-000000000060")

    now = datetime.now(UTC)

    async with async_session_factory() as session:
        for src_data in SAMPLE_SOURCES:
            existing = await session.get(Source, src_data["source_id"])
            if not existing:
                session.add(Source(**src_data))

        if not await session.get(Tenant, tenant_id):
            session.add(Tenant(tenant_id=tenant_id, name="Default Tenant", active=True))

        if not await session.get(User, user_id):
            session.add(
                User(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    email="analyst@example.com",
                    role="analyst",
                    active=True,
                )
            )

        if not await session.get(CanonicalDocument, document_id):
            body = (
                "The Federal Open Market Committee decided to maintain the target range "
                "for the federal funds rate at 5-1/4 to 5-1/2 percent. Inflation remains "
                "somewhat elevated. The Committee is strongly committed to returning inflation "
                "to its 2 percent objective."
            )
            session.add(
                CanonicalDocument(
                    document_id=document_id,
                    source_id="fed",
                    external_id="monetary20240320a",
                    canonical_url="https://www.federalreserve.gov/newsevents/pressreleases/monetary20240320a.htm",
                    title="Federal Reserve issues FOMC statement on inflation and monetary policy",
                    body=body,
                    summary=body[:200],
                    language="en",
                    published_at=now - timedelta(days=1),
                    retrieved_at=now,
                    document_type="press_release",
                    country_codes=["US"],
                    topic_labels=["monetary_policy", "inflation"],
                    content_hash="seed_doc_hash_001",
                    parser_version="0.1.0",
                    source_record_id="fed",
                    is_canonical=True,
                )
            )

        if not await session.get(Entity, entity_id):
            session.add(
                Entity(
                    entity_id=entity_id,
                    canonical_name="Federal Reserve",
                    entity_type="organization",
                    country_codes=["US"],
                    external_ids={"wikidata": "Q53536"},
                    attributes={"sector": "central_bank"},
                )
            )

        if not await session.get(EvidenceSpan, evidence_id):
            evidence_text = (
                "the Committee decided to maintain the target range for the federal funds rate "
                "at 5-1/4 to 5-1/2 percent"
            )
            session.add(
                EvidenceSpan(
                    evidence_id=evidence_id,
                    document_id=document_id,
                    start_offset=0,
                    end_offset=len(evidence_text),
                    text=evidence_text,
                    source_url="https://www.federalreserve.gov/newsevents/pressreleases/monetary20240320a.htm",
                    model_version="rule-v0.1.0",
                    confidence=0.95,
                )
            )

        if not await session.get(Event, event_id):
            session.add(
                Event(
                    event_id=event_id,
                    document_id=document_id,
                    event_type="monetary_policy_decision",
                    action="maintained_interest_rate",
                    object_name="federal funds rate",
                    magnitude=5.375,
                    unit="percent",
                    event_time=now - timedelta(days=1),
                    confidence=0.92,
                    extraction_model_version="rule-v0.1.0",
                )
            )
            session.add(EventEvidence(event_id=event_id, evidence_id=evidence_id))

        if not await session.get(Narrative, narrative_id):
            session.add(
                Narrative(
                    narrative_id=narrative_id,
                    title="Federal Reserve maintains hawkish stance on inflation",
                    description=(
                        "The Federal Reserve continues to hold interest rates steady while "
                        "signaling commitment to bringing inflation back to the 2% target."
                    ),
                    lifecycle_state="established",
                    topic_labels=["monetary_policy", "inflation"],
                    started_at=now - timedelta(days=30),
                    last_updated_at=now,
                    velocity_score=0.65,
                    novelty_score=0.3,
                    source_diversity_score=0.8,
                    market_relevance_score=0.9,
                    sentiment_score=-0.2,
                    clustering_version="0.1.0",
                )
            )
            session.add(NarrativeEvent(narrative_id=narrative_id, event_id=event_id))

        if not await session.get(Signal, signal_id):
            signal_data = calculate_signal(
                signal_type="central_bank_hawkishness",
                event_confidence=0.92,
                source_credibility=0.95,
                asset_relevance=0.85,
                severity=0.7,
                novelty=0.3,
                narrative_momentum=0.65,
                event_time=now - timedelta(days=1),
                evidence_ids=[evidence_id],
                event_ids=[event_id],
                narrative_ids=[narrative_id],
            )
            session.add(
                Signal(
                    signal_id=signal_id,
                    signal_type="central_bank_hawkishness",
                    entity_id=entity_id,
                    asset_id="USD",
                    direction=signal_data["direction"],
                    score=signal_data["score"],
                    confidence=signal_data["confidence"],
                    horizon="short_term",
                    generated_at=now,
                    expires_at=now + timedelta(days=7),
                    calculation_version=signal_data["calculation_version"],
                    component_scores=signal_data["component_scores"],
                )
            )
            session.add(SignalEvidence(signal_id=signal_id, evidence_id=evidence_id))

        await session.commit()

    search = SearchService()
    await search.ensure_indices()
    await search.index_document(
        {
            "document_id": str(document_id),
            "source_id": "fed",
            "title": "Federal Reserve issues FOMC statement on inflation and monetary policy",
            "body": (
                "The Federal Open Market Committee decided to maintain the target range "
                "for the federal funds rate. Inflation remains somewhat elevated."
            ),
            "summary": "Fed maintains rates, inflation remains elevated",
            "language": "en",
            "published_at": (now - timedelta(days=1)).isoformat(),
            "retrieved_at": now.isoformat(),
            "document_type": "press_release",
            "country_codes": ["US"],
            "topic_labels": ["monetary_policy", "inflation"],
            "content_hash": "seed_doc_hash_001",
        }
    )
    await search.close()
    print("Seed data created successfully.")
    print(f"  Document: {document_id}")
    print(f"  Event:    {event_id}")
    print(f"  Signal:   {signal_id}")
    print(f"  Narrative: {narrative_id}")
    _ = FED_PRESS_RELEASE_HTML  # fixture available for connector tests


if __name__ == "__main__":
    asyncio.run(seed())
