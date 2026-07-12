"""Transparent signal calculation engine."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

CALCULATION_VERSION = "0.1.0"

SIGNAL_TYPES = [
    "oil_supply_risk",
    "natural_gas_supply_risk",
    "sanctions_escalation",
    "central_bank_hawkishness",
    "inflation_pressure",
    "supply_chain_disruption",
    "political_instability",
    "severe_weather_exposure",
    "corporate_earnings_risk",
]


def normalize_score(raw_score: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    if max_val == min_val:
        return 0.0
    normalized = (raw_score - min_val) / (max_val - min_val)
    return max(0.0, min(1.0, normalized))


def time_decay(event_time: datetime | None, half_life_hours: float = 72.0) -> float:
    if not event_time:
        return 0.5
    now = datetime.now(UTC)
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=UTC)
    hours_elapsed = (now - event_time).total_seconds() / 3600
    return 0.5 ** (hours_elapsed / half_life_hours)


def calculate_signal(
    *,
    signal_type: str,
    event_confidence: float,
    source_credibility: float,
    asset_relevance: float,
    severity: float,
    novelty: float,
    narrative_momentum: float,
    event_time: datetime | None = None,
    evidence_ids: list[UUID],
    event_ids: list[UUID] | None = None,
    narrative_ids: list[UUID] | None = None,
) -> dict[str, Any]:
    if not evidence_ids:
        raise ValueError("Signals require at least one evidence span")

    component_scores = {
        "event_confidence": event_confidence,
        "source_credibility": source_credibility,
        "asset_relevance": asset_relevance,
        "severity": severity,
        "novelty": novelty,
        "narrative_momentum": narrative_momentum,
    }

    raw_score = (
        event_confidence
        * source_credibility
        * asset_relevance
        * severity
        * novelty
        * narrative_momentum
    )
    decay = time_decay(event_time)
    final_score = normalize_score(raw_score) * decay

    direction = "negative" if severity > 0.5 else "neutral"
    if signal_type in ("central_bank_hawkishness", "inflation_pressure"):
        direction = "negative" if final_score > 0.5 else "positive"

    confidence = min(event_confidence, source_credibility) * 0.9

    return {
        "signal_id": str(uuid4()),
        "signal_type": signal_type,
        "direction": direction,
        "score": round(final_score, 4),
        "confidence": round(confidence, 4),
        "horizon": "short_term",
        "generated_at": datetime.now(UTC).isoformat(),
        "expires_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        "narrative_ids": [str(n) for n in (narrative_ids or [])],
        "event_ids": [str(e) for e in (event_ids or [])],
        "evidence_ids": [str(e) for e in evidence_ids],
        "calculation_version": CALCULATION_VERSION,
        "component_scores": {k: round(v, 4) for k, v in component_scores.items()},
    }
