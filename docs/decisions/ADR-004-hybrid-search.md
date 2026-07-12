# ADR-004: OpenSearch plus pgvector for Hybrid Search

## Status
Accepted

## Context
Analysts need keyword and semantic search across documents, events, and narratives.

## Decision
Use OpenSearch for full-text search and pgvector for vector similarity (MVP).

## Consequences
- Hybrid retrieval with reciprocal rank fusion
- Separate index management workflows required
