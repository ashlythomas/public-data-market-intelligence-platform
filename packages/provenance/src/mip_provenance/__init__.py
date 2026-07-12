from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID


@dataclass
class ProvenanceChain:
    source_id: str
    document_id: UUID
    evidence_ids: list[UUID] = field(default_factory=list)
    processing_run_id: UUID | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    calculation_version: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "document_id": str(self.document_id),
            "evidence_ids": [str(e) for e in self.evidence_ids],
            "processing_run_id": str(self.processing_run_id) if self.processing_run_id else None,
            "model_version": self.model_version,
            "prompt_version": self.prompt_version,
            "calculation_version": self.calculation_version,
            "created_at": self.created_at.isoformat(),
        }
