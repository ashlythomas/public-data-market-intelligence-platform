# ADR-006: Evidence-First Event Extraction

## Status
Accepted

## Context
All intelligence outputs must be explainable and auditable.

## Decision
Reject events without at least one evidence span linking to source text.

## Consequences
- LLM outputs validated for evidence before acceptance
- Invalid outputs sent to DLQ after one repair attempt
