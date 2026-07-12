"""Event clustering, narrative detection, and signal generation."""

import uuid
from datetime import UTC, datetime, timedelta

from mip_database.models import (
    Event,
    Narrative,
    NarrativeEvent,
    Signal,
    SignalEvidence,
)
from mip_database.repositories import EventRepository
from mip_signal_engine import calculate_signal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

CLUSTERING_VERSION = "0.1.0"

ASSET_RELEVANCE_BY_EVENT: dict[str, float] = {
    "monetary_policy_decision": 0.9,
    "inflation_update": 0.85,
    "corporate_filing": 0.75,
    "geopolitical_event": 0.7,
}


async def cluster_events(session: AsyncSession, event_ids: list[uuid.UUID]) -> uuid.UUID:
    """Cluster events by type and time proximity; return cluster representative."""
    if not event_ids:
        return uuid.uuid4()

    result = await session.execute(select(Event).where(Event.event_id.in_(event_ids)))
    events = list(result.scalars().all())
    if not events:
        return uuid.uuid4()

    event_repo = EventRepository(session)
    clusters: dict[str, list[Event]] = {}
    for event in events:
        similar = await event_repo.find_similar(event.event_type, within_hours=72, limit=20)
        cluster_key = event.event_type
        cluster_members = [event, *similar]
        clusters[cluster_key] = cluster_members

    largest = max(clusters.values(), key=len, default=events)
    return largest[0].event_id


async def update_narrative(
    session: AsyncSession,
    event: Event,
    topic_labels: list[str],
    sentiment_score: float = 0.0,
) -> Narrative:
    """Create or update narrative for related events."""
    result = await session.execute(
        select(Narrative)
        .where(Narrative.lifecycle_state.in_(["emerging", "accelerating", "established"]))
        .order_by(Narrative.last_updated_at.desc())
        .limit(10)
    )
    candidates = list(result.scalars().all())
    existing = next(
        (
            n
            for n in candidates
            if set(topic_labels) & set(n.topic_labels)
            or event.event_type.split("_")[0] in n.topic_labels
        ),
        None,
    )
    now = datetime.now(UTC)

    if existing:
        existing.last_updated_at = now
        existing.velocity_score = min(1.0, existing.velocity_score + 0.1)
        existing.sentiment_score = (existing.sentiment_score + sentiment_score) / 2
        session.add(NarrativeEvent(narrative_id=existing.narrative_id, event_id=event.event_id))
        return existing

    narrative = Narrative(
        narrative_id=uuid.uuid4(),
        title=f"Emerging narrative: {topic_labels[0] if topic_labels else event.event_type}",
        description=f"Cluster of related {event.event_type} events",
        lifecycle_state="emerging",
        topic_labels=topic_labels,
        started_at=now,
        last_updated_at=now,
        velocity_score=0.5,
        novelty_score=0.7,
        source_diversity_score=0.5,
        market_relevance_score=ASSET_RELEVANCE_BY_EVENT.get(event.event_type, 0.5),
        sentiment_score=sentiment_score,
        clustering_version=CLUSTERING_VERSION,
    )
    session.add(narrative)
    session.add(NarrativeEvent(narrative_id=narrative.narrative_id, event_id=event.event_id))
    return narrative


async def generate_signal_for_event(
    session: AsyncSession,
    event: Event,
    narrative: Narrative,
    evidence_ids: list[uuid.UUID],
    *,
    source_credibility: float = 0.9,
    sentiment_score: float = 0.0,
) -> Signal:
    signal_type_map = {
        "monetary_policy_decision": "central_bank_hawkishness",
        "inflation_update": "inflation_pressure",
        "corporate_filing": "corporate_earnings_risk",
    }
    signal_type = signal_type_map.get(event.event_type, "political_instability")

    asset_relevance = ASSET_RELEVANCE_BY_EVENT.get(
        event.event_type, narrative.market_relevance_score
    )
    severity = (
        event.magnitude if event.magnitude is not None else min(1.0, abs(sentiment_score) + 0.3)
    )

    signal_data = calculate_signal(
        signal_type=signal_type,
        event_confidence=event.confidence,
        source_credibility=source_credibility,
        asset_relevance=asset_relevance,
        severity=severity,
        novelty=narrative.novelty_score,
        narrative_momentum=narrative.velocity_score,
        event_time=event.event_time,
        evidence_ids=evidence_ids,
        event_ids=[event.event_id],
        narrative_ids=[narrative.narrative_id],
    )

    signal = Signal(
        signal_id=uuid.UUID(signal_data["signal_id"]),
        signal_type=signal_type,
        direction=signal_data["direction"],
        score=signal_data["score"],
        confidence=signal_data["confidence"],
        horizon=signal_data["horizon"],
        generated_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=7),
        calculation_version=signal_data["calculation_version"],
        component_scores=signal_data["component_scores"],
    )
    session.add(signal)
    for eid in evidence_ids:
        session.add(SignalEvidence(signal_id=signal.signal_id, evidence_id=eid))
    return signal
