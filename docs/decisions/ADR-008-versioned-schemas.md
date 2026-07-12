# ADR-008: Versioned Domain Schemas

## Status
Accepted

## Context
Kafka messages and API responses must maintain backward compatibility.

## Decision
All domain schemas live in `packages/schemas` with Pydantic v2 and explicit schema versions.

## Consequences
- Schema changes require version bumps
- JSON Schema generation available for contract tests
