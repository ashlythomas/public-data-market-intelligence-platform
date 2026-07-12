from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ExtractedEvent(BaseModel):
    event_id: UUID
    document_id: UUID
    event_type: str
    actor_entity_ids: list[UUID] = Field(default_factory=list)
    target_entity_ids: list[UUID] = Field(default_factory=list)
    action: str
    object_name: str | None = None
    magnitude: float | None = None
    unit: str | None = None
    event_time: datetime | None = None
    effective_time: datetime | None = None
    location_entity_ids: list[UUID] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[UUID] = Field(min_length=1)
    extraction_model_version: str
    prompt_version: str | None = None
