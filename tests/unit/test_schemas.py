"""Unit tests for domain schemas."""

import uuid
from datetime import UTC, datetime

import pytest
from mip_schemas.documents import CanonicalDocument, EvidenceSpan, RawDocumentEnvelope
from mip_schemas.events import ExtractedEvent
from mip_schemas.signals import Signal
from pydantic import ValidationError


def test_raw_document_envelope_valid():
    doc = RawDocumentEnvelope(
        ingestion_id=uuid.uuid4(),
        source_id="fed",
        source_url="https://example.com",
        retrieved_at=datetime.now(UTC),
        content_type="text/html",
        object_store_uri="s3://bucket/key",
        content_hash="abc123",
        connector_version="0.1.0",
    )
    assert doc.source_id == "fed"


def test_extracted_event_requires_evidence():
    with pytest.raises(ValidationError):
        ExtractedEvent(
            event_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            event_type="policy",
            action="announced",
            confidence=0.9,
            evidence_ids=[],
            extraction_model_version="0.1.0",
        )


def test_signal_requires_evidence():
    with pytest.raises(ValidationError):
        Signal(
            signal_id=uuid.uuid4(),
            signal_type="inflation_pressure",
            direction="negative",
            score=0.7,
            confidence=0.8,
            horizon="short_term",
            generated_at=datetime.now(UTC),
            evidence_ids=[],
            calculation_version="0.1.0",
        )


def test_canonical_document():
    doc = CanonicalDocument(
        document_id=uuid.uuid4(),
        source_id="fed",
        canonical_url="https://example.com",
        body="Test content",
        retrieved_at=datetime.now(UTC),
        content_hash="hash",
        parser_version="0.1.0",
        source_record_id="fed",
    )
    assert doc.language == "en"


def test_evidence_span_offsets():
    span = EvidenceSpan(
        evidence_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        start_offset=0,
        end_offset=10,
        text="sample",
        source_url="https://example.com",
        model_version="0.1.0",
        confidence=0.95,
    )
    assert span.end_offset >= span.start_offset
