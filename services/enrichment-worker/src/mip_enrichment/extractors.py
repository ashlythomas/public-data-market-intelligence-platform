"""Rule-based and gateway-backed NLP enrichment."""

import re
import uuid
from typing import Any

TAXONOMY_KEYWORDS: dict[str, list[str]] = {
    "monetary_policy": ["federal reserve", "interest rate", "fomc", "central bank", "ecb"],
    "inflation": ["inflation", "cpi", "price index", "deflation"],
    "employment": ["employment", "unemployment", "jobs", "labor market"],
    "corporate_earnings": ["earnings", "revenue", "quarterly results", "10-k", "8-k"],
    "energy": ["oil", "natural gas", "crude", "opec", "energy"],
    "geopolitics": ["sanctions", "tariff", "trade war", "geopolitical"],
    "regulation": ["regulation", "sec", "compliance", "rulemaking"],
}

ENTITY_PATTERNS: list[tuple[str, str]] = [
    ("organization", r"\b(Federal Reserve|ECB|SEC|OPEC|FOMC)\b"),
    ("organization", r"\b([A-Z][a-z]+ (?:Corp|Inc|LLC|Ltd))\b"),
    ("country", r"\b(United States|China|Russia|European Union)\b"),
]


def extract_entities(text: str, document_id: uuid.UUID) -> list[dict[str, Any]]:
    mentions = []
    for entity_type, pattern in ENTITY_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            mentions.append(
                {
                    "mention_id": str(uuid.uuid4()),
                    "document_id": str(document_id),
                    "text": match.group(0),
                    "entity_type": entity_type,
                    "start_offset": match.start(),
                    "end_offset": match.end(),
                    "extraction_confidence": 0.85,
                    "model_version": "rule-v0.1.0",
                }
            )
    return mentions


def classify_topics(text: str, threshold: float = 0.3) -> list[dict[str, Any]]:
    text_lower = text.lower()
    labels = []
    for label, keywords in TAXONOMY_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text_lower)
        if hits > 0:
            confidence = min(1.0, hits / len(keywords) + 0.3)
            if confidence >= threshold:
                labels.append({"label": label, "confidence": round(confidence, 3)})
    return labels


def extract_events(
    text: str,
    document_id: uuid.UUID,
    source_url: str,
) -> list[dict[str, Any]]:
    events = []
    patterns = [
        (
            "monetary_policy_decision",
            r"(decided to maintain|raised|lowered|cut|hiked).{0,80}(interest rate|federal funds)",
            "rate_decision",
        ),
        (
            "corporate_filing",
            r"(filed|reported|announced).{0,60}(8-k|10-k|earnings|quarterly)",
            "filing_reported",
        ),
        (
            "inflation_update",
            r"inflation.{0,40}(elevated|rising|declining|target)",
            "inflation_assessment",
        ),
    ]
    for event_type, pattern, action in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            evidence_id = uuid.uuid4()
            events.append(
                {
                    "event_id": str(uuid.uuid4()),
                    "document_id": str(document_id),
                    "event_type": event_type,
                    "action": action,
                    "confidence": 0.8,
                    "magnitude": 0.6,
                    "evidence_ids": [str(evidence_id)],
                    "extraction_model_version": "rule-v0.1.0",
                    "evidence": {
                        "evidence_id": str(evidence_id),
                        "document_id": str(document_id),
                        "start_offset": match.start(),
                        "end_offset": match.end(),
                        "text": match.group(0),
                        "source_url": source_url,
                        "model_version": "rule-v0.1.0",
                        "confidence": 0.85,
                    },
                }
            )
    return events


def score_sentiment(text: str) -> dict[str, float]:
    hawkish = len(re.findall(r"\b(hawkish|tighten|raise|elevated|restrictive)\b", text, re.I))
    dovish = len(re.findall(r"\b(dovish|ease|cut|accommodative|stimulus)\b", text, re.I))
    total = hawkish + dovish + 1
    return {
        "hawkish_dovish": (hawkish - dovish) / total,
        "severity": min(1.0, hawkish / total),
        "market_surprise": 0.3,
    }
