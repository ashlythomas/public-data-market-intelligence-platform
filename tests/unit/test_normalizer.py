"""Unit tests for document normalization."""

import uuid

from mip_normalizer.parser import (
    detect_language,
    extract_html,
    extract_json,
    normalize_document,
    normalize_unicode,
)
from mip_test_fixtures import FED_PRESS_RELEASE_HTML


def test_normalize_unicode():
    assert normalize_unicode("café") == "café"


def test_detect_language_english():
    assert detect_language("The Federal Reserve announced policy changes") == "en"


def test_extract_html():
    body, title = extract_html(FED_PRESS_RELEASE_HTML)
    assert "Federal Open Market Committee" in body
    assert title is not None
    assert "FOMC" in title


def test_extract_json():
    content = '{"title": "Test", "body": "Content here with enough text to pass validation checks for the normalizer service."}'
    body, title = extract_json(content)
    assert title == "Test"
    assert "Content here" in body


def test_normalize_document_html():
    envelope = {
        "source_id": "fed",
        "source_url": "https://fed.gov/test",
        "content_type": "text/html",
        "content_hash": "abc",
        "retrieved_at": "2024-01-01T00:00:00Z",
        "metadata": {},
    }
    result = normalize_document(raw_envelope=envelope, content=FED_PRESS_RELEASE_HTML.encode())
    assert result is not None
    assert result["source_id"] == "fed"
    assert len(result["body"]) > 50


def test_normalize_document_rejects_empty():
    envelope = {
        "source_id": "fed",
        "source_url": "https://fed.gov/test",
        "content_type": "text/plain",
        "content_hash": "abc",
        "retrieved_at": "2024-01-01T00:00:00Z",
    }
    result = normalize_document(raw_envelope=envelope, content=b"short")
    assert result is None


def test_normalize_document_uses_ingestion_id():
    ingestion_id = uuid.uuid4()
    envelope = {
        "ingestion_id": str(ingestion_id),
        "source_id": "fed",
        "source_url": "https://fed.gov/test",
        "content_type": "text/html",
        "content_hash": "abc123",
        "retrieved_at": "2024-01-01T00:00:00Z",
        "metadata": {},
    }
    result = normalize_document(raw_envelope=envelope, content=FED_PRESS_RELEASE_HTML.encode())
    assert result is not None
    assert result["document_id"] == str(ingestion_id)


def test_normalize_document_idempotent_without_ingestion_id():
    envelope = {
        "source_id": "fed",
        "source_url": "https://fed.gov/test",
        "content_type": "text/html",
        "content_hash": "stable-hash",
        "retrieved_at": "2024-01-01T00:00:00Z",
        "metadata": {},
    }
    first = normalize_document(raw_envelope=envelope, content=FED_PRESS_RELEASE_HTML.encode())
    second = normalize_document(raw_envelope=envelope, content=FED_PRESS_RELEASE_HTML.encode())
    assert first is not None and second is not None
    assert first["document_id"] == second["document_id"]
