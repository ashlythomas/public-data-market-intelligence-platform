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
from mip_signal_engine import calculate_signal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

CLUSTERING_VERSION = "0.1.0"


async def cluster_events(session: AsyncSession, event_ids: list[uuid.UUID]) -> uuid.UUID:
    """Simple event clustering by event_type and time proximity."""
    if not event_ids:
        return uuid.uuid4()
    result = await session.execute(select(Event).where(Event.event_id.in_(event_ids)))
    events = list(result.scalars().all())
    if not events:
        return uuid.uuid4()
    return events[0].event_id


async def update_narrative(
    session: AsyncSession,
    event: Event,
    topic_labels: list[str],
) -> Narrative:
    """Create or update narrative for related events."""
    result = await session.execute(
        select(Narrative)
        .where(Narrative.lifecycle_state.in_(["emerging", "accelerating", "established"]))
        .order_by(Narrative.last_updated_at.desc())
        .limit(5)
    )
    candidates = list(result.scalars().all())
    existing = next(
        (n for n in candidates if any(t in n.topic_labels for t in topic_labels)),
        None,
    )
    now = datetime.now(UTC)

    if existing:
        existing.last_updated_at = now
        existing.velocity_score = min(1.0, existing.velocity_score + 0.1)
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
        market_relevance_score=0.6,
        sentiment_score=0.0,
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
    source_credibility: float = 0.9,
) -> Signal:
    signal_type_map = {
        "monetary_policy_decision": "central_bank_hawkishness",
        "inflation_update": "inflation_pressure",
        "corporate_filing": "corporate_earnings_risk",
    }
    signal_type = signal_type_map.get(event.event_type, "political_instability")

    signal_data = calculate_signal(
        signal_type=signal_type,
        event_confidence=event.confidence,
        source_credibility=source_credibility,
        asset_relevance=0.7,
        severity=0.6,
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
