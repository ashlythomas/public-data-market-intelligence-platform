from pydantic import BaseModel, Field


class SourceRecord(BaseModel):
    source_id: str
    source_name: str
    source_type: str
    jurisdiction: str | None = None
    homepage_url: str | None = None
    credibility_score: float = Field(ge=0.0, le=1.0, default=0.5)
    licence_type: str
    redistribution_allowed: bool = True
    commercial_use_allowed: bool = True
    active: bool = True
