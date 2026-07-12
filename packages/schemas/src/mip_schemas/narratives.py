from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class Narrative(BaseModel):
    narrative_id: UUID
    title: str
    description: str
    lifecycle_state: str
    topic_labels: list[str] = Field(default_factory=list)
    entity_ids: list[UUID] = Field(default_factory=list)
    event_ids: list[UUID] = Field(default_factory=list)
    started_at: datetime
    last_updated_at: datetime
    velocity_score: float = Field(ge=0.0)
    novelty_score: float = Field(ge=0.0, le=1.0)
    source_diversity_score: float = Field(ge=0.0, le=1.0)
    market_relevance_score: float = Field(ge=0.0, le=1.0)
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    clustering_version: str
