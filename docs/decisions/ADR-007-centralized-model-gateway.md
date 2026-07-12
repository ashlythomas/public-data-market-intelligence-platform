# ADR-007: Centralized Model Gateway

## Status
Accepted

## Context
Multiple services need LLM and embedding access with consistent versioning and cost tracking.

## Decision
All model provider calls route through an internal model gateway service.

## Consequences
- Application services never call vendors directly
- Prompt and model versions tracked centrally
