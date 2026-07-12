# ADR-009: Transparent Signal Formulas for MVP

## Status
Accepted

## Context
Signals must be explainable to analysts and auditable for compliance.

## Decision
Use weighted, configuration-driven formulas with exposed component scores for MVP.

## Consequences
- No black-box ML for initial signal generation
- Historical replay is deterministic for fixed inputs
