from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RawDocumentEnvelope(BaseModel):
    ingestion_id: UUID
    source_id: str
    external_id: str | None = None
    source_url: str
    retrieved_at: datetime
    published_at: datetime | None = None
    content_type: str
    language_hint: str | None = None
    object_store_uri: str
    content_hash: str
    connector_version: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CanonicalDocument(BaseModel):
    document_id: UUID
    source_id: str
    external_id: str | None = None
    canonical_url: str
    title: str | None = None
    body: str
    summary: str | None = None
    authors: list[str] = Field(default_factory=list)
    language: str = "en"
    translated_body: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime
    document_type: str = "article"
    country_codes: list[str] = Field(default_factory=list)
    topic_labels: list[str] = Field(default_factory=list)
    content_hash: str
    parser_version: str
    source_record_id: str


class EvidenceSpan(BaseModel):
    evidence_id: UUID
    document_id: UUID
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    text: str
    source_url: str
    model_version: str
    confidence: float = Field(ge=0.0, le=1.0)
