from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class Signal(BaseModel):
    signal_id: UUID
    signal_type: str
    entity_id: UUID | None = None
    asset_id: str | None = None
    direction: str
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    horizon: str
    generated_at: datetime
    expires_at: datetime | None = None
    narrative_ids: list[UUID] = Field(default_factory=list)
    event_ids: list[UUID] = Field(default_factory=list)
    evidence_ids: list[UUID] = Field(min_length=1)
    calculation_version: str
    component_scores: dict[str, float] = Field(default_factory=dict)
