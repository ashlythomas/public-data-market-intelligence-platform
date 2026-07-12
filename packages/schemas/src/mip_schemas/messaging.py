from datetime import UTC, datetime
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

T = TypeVar("T")


class MessageEnvelope(BaseModel, Generic[T]):
    message_id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID = Field(default_factory=uuid4)
    causation_id: UUID | None = None
    schema_version: str = "1.0"
    event_type: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    producer: str
    producer_version: str
    payload: T
    trace_id: str = Field(default_factory=lambda: str(uuid4()))


class KafkaMessage(BaseModel):
    """Standard Kafka message wrapper."""

    message_id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID = Field(default_factory=uuid4)
    causation_id: UUID | None = None
    schema_version: str = "1.0"
    event_type: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    producer: str
    producer_version: str
    payload: dict[str, Any]
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
