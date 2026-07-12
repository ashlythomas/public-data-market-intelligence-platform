# ADR-003: PostgreSQL as Operational System of Record

## Status
Accepted

## Context
The platform needs ACID transactions, relational queries, and tenant isolation.

## Decision
Use PostgreSQL with pgvector extension for operational data and MVP vector search.

## Consequences
- Alembic migrations for all schema changes
- Repository layer abstracts database access
- Cross-service direct database access is prohibited
