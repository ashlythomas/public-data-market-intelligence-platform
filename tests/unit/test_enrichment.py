"""Tests for enrichment extractors."""

import uuid

from mip_enrichment.extractors import (
    classify_topics,
    extract_entities,
    extract_events,
    score_sentiment,
)


def test_extract_entities_fed():
    text = "The Federal Reserve announced policy changes today."
    doc_id = uuid.uuid4()
    entities = extract_entities(text, doc_id)
    assert len(entities) >= 1
    assert any("Federal Reserve" in e["text"] for e in entities)


def test_classify_topics_inflation():
    text = "Inflation remains elevated according to the CPI report."
    topics = classify_topics(text)
    labels = [t["label"] for t in topics]
    assert "inflation" in labels


def test_extract_events_with_evidence():
    text = "The Committee decided to maintain the target range for the federal funds rate."
    doc_id = uuid.uuid4()
    events = extract_events(text, doc_id, "https://example.com")
    assert len(events) >= 1
    assert events[0]["evidence_ids"]
    assert "evidence" in events[0]


def test_score_sentiment_hawkish():
    text = "The Fed remains hawkish and may tighten policy further."
    scores = score_sentiment(text)
    assert scores["hawkish_dovish"] > 0
