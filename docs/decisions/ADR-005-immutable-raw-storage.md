# ADR-005: Immutable Raw Object Storage

## Status
Accepted

## Context
Raw source data must be retained immutably for reprocessing and audit.

## Decision
Store original payloads in S3-compatible object storage with content-addressed paths.

## Consequences
- Duplicate payloads detected by content hash
- Reprocessing uses ingestion ID, never overwrites raw data
