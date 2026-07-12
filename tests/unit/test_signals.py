"""Unit tests for signal calculation."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from mip_api.signals import calculate_signal, normalize_score, time_decay


def test_normalize_score():
    assert normalize_score(0.5) == 0.5
    assert normalize_score(1.5) == 1.0
    assert normalize_score(-0.5) == 0.0


def test_time_decay_recent():
    recent = datetime.now(UTC) - timedelta(hours=1)
    decay = time_decay(recent)
    assert decay > 0.9


def test_time_decay_old():
    old = datetime.now(UTC) - timedelta(days=30)
    decay = time_decay(old)
    assert decay < 0.1


def test_calculate_signal_requires_evidence():
    with pytest.raises(ValueError, match="evidence"):
        calculate_signal(
            signal_type="inflation_pressure",
            event_confidence=0.9,
            source_credibility=0.9,
            asset_relevance=0.8,
            severity=0.7,
            novelty=0.5,
            narrative_momentum=0.6,
            evidence_ids=[],
        )


def test_calculate_signal_deterministic():
    evidence = [uuid.uuid4()]
    kwargs = dict(
        signal_type="central_bank_hawkishness",
        event_confidence=0.92,
        source_credibility=0.95,
        asset_relevance=0.85,
        severity=0.7,
        novelty=0.3,
        narrative_momentum=0.65,
        event_time=datetime(2024, 3, 20, tzinfo=UTC),
        evidence_ids=evidence,
    )
    result1 = calculate_signal(**kwargs)
    result2 = calculate_signal(**kwargs)
    assert result1["score"] == result2["score"]
    assert result1["direction"] == result2["direction"]
    assert "component_scores" in result1


def test_calculate_signal_component_scores():
    result = calculate_signal(
        signal_type="inflation_pressure",
        event_confidence=0.8,
        source_credibility=0.9,
        asset_relevance=0.7,
        severity=0.6,
        novelty=0.4,
        narrative_momentum=0.5,
        evidence_ids=[uuid.uuid4()],
    )
    assert len(result["component_scores"]) == 6
    assert all(0 <= v <= 1 for v in result["component_scores"].values())
