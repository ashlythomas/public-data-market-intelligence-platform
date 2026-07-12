# ADR-010: Licence-Aware Serving

## Status
Accepted

## Context
Public data sources have varying redistribution and commercial use restrictions.

## Decision
Enforce licence policies at API serving time, filtering content and limiting excerpts.

## Consequences
- Every source carries licence metadata
- API layer logs licence policy decisions
