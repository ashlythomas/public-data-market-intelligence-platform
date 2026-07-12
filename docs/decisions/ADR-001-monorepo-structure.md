# ADR-001: Monorepo Structure

## Status
Accepted

## Context
The market intelligence platform has many interdependent services, shared schemas, and coordinated deployments.

## Decision
Use a single monorepo with `apps/`, `services/`, `packages/`, `workflows/`, and `infra/` directories.

## Consequences
- Atomic schema changes across services
- Simplified local development with shared tooling
- Requires disciplined package boundaries
