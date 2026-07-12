"""Contract tests for Kafka message format."""

import uuid

from mip_messaging import wrap_payload
from mip_schemas.messaging import KafkaMessage


def test_kafka_message_required_fields():
    msg = KafkaMessage(
        event_type="raw.document.ingested",
        producer="fed-connector",
        producer_version="0.1.0",
        payload={"source_id": "fed"},
    )
    assert msg.message_id is not None
    assert msg.correlation_id is not None
    assert msg.schema_version == "1.0"
    assert msg.trace_id is not None


def test_wrap_payload():
    payload = {"ingestion_id": str(uuid.uuid4()), "source_id": "fed"}
    wrapped = wrap_payload(
        payload,
        event_type="raw.document.ingested",
        producer="fed-connector",
        producer_version="0.1.0",
    )
    assert wrapped["event_type"] == "raw.document.ingested"
    assert wrapped["producer"] == "fed-connector"
    assert "payload" in wrapped
    assert "message_id" in wrapped
    assert "occurred_at" in wrapped
