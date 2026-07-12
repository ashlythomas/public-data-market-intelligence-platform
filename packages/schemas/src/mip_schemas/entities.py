from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EntityMention(BaseModel):
    mention_id: UUID
    document_id: UUID
    text: str
    entity_type: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    canonical_entity_id: UUID | None = None
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    linking_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    model_version: str


class CanonicalEntity(BaseModel):
    entity_id: UUID
    canonical_name: str
    entity_type: str
    aliases: list[str] = Field(default_factory=list)
    country_codes: list[str] = Field(default_factory=list)
    external_ids: dict[str, str] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
