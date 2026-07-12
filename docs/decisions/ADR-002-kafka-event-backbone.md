# ADR-002: Kafka as Event Backbone

## Status
Accepted

## Context
The platform requires near-real-time ingestion, replay capability, and decoupled processing stages.

## Decision
Use Apache Kafka with versioned topics for raw ingestion and processing pipelines.

## Consequences
- All consumers must be idempotent
- DLQ topics required for failure handling
- Message envelopes include correlation and trace IDs
