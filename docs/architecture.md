# Market Intelligence Platform Architecture

This document describes the current architecture of the Market Intelligence Platform and how data moves from source ingestion to API delivery and alerting.

## Architecture Diagram

```mermaid
flowchart LR
    subgraph Sources["External Sources"]
        FED["FED"]
        FRED["FRED"]
        SEC["SEC EDGAR"]
        GDELT["GDELT"]
    end

    subgraph Connectors["Connector Services"]
        C1["fed connector"]
        C2["fred connector"]
        C3["sec-edgar connector"]
        C4["gdelt connector"]
    end

    subgraph Infra["Core Infrastructure"]
        S3["S3 Raw Storage"]
        DB["PostgreSQL"]
        KAFKA["Kafka Topics + DLQs"]
        OS["OpenSearch"]
        REDIS["Redis"]
    end

    subgraph Workers["Pipeline Workers"]
        NORM["normalizer"]
        ENRICH["enrichment-worker"]
        INTEL["intelligence-worker"]
        ALERT["alert-worker"]
    end

    subgraph Serving["Serving Layer"]
        API["API Service"]
    end

    FED --> C1
    FRED --> C2
    SEC --> C3
    GDELT --> C4

    C1 --> S3
    C2 --> S3
    C3 --> S3
    C4 --> S3

    C1 --> DB
    C2 --> DB
    C3 --> DB
    C4 --> DB

    C1 --> KAFKA
    C2 --> KAFKA
    C3 --> KAFKA
    C4 --> KAFKA

    KAFKA --> NORM
    NORM --> DB
    NORM --> OS
    NORM --> KAFKA

    KAFKA --> ENRICH
    ENRICH --> DB
    ENRICH --> KAFKA

    KAFKA --> INTEL
    INTEL --> DB
    INTEL --> KAFKA

    KAFKA --> ALERT
    ALERT --> DB

    API --> DB
    API --> OS
    API --> REDIS
```

## 1. System Goals

- Ingest public market-relevant content from multiple sources.
- Normalize and enrich documents into structured signals.
- Preserve provenance and tenant isolation across all pipeline stages.
- Expose search, analytics, and alerting via API.

## 2. High-Level Topology

The platform is organized as a monorepo with three major layers:

- `services/`: asynchronous workers and source connectors
- `apps/`: API and user-facing worker processes
- `packages/`: shared libraries for schemas, persistence, messaging, observability, and policy logic

Core infrastructure:

- Kafka for event backbone and decoupled processing
- PostgreSQL for operational persistence
- S3-compatible object storage for immutable raw payloads
- OpenSearch for retrieval/search
- Redis for distributed API rate limiting

## 2.1 Source Profiles: Data and Signal Characteristics

### FED (Federal Reserve)

- **Primary data type**: central bank press releases, policy statements, speeches, and announcements.
- **Typical content shape**: long-form HTML text with formal policy language and publication dates.
- **High-value extracted signals**:
  - monetary policy actions (rate hold/hike/cut)
  - balance sheet and liquidity actions
  - forward guidance tone shifts (hawkish/dovish)
- **Operational notes**:
  - strong source credibility for macro policy events
  - lower document volume, high significance per item

### FRED (Federal Reserve Economic Data)

- **Primary data type**: economic data release feeds and macroeconomic publication updates.
- **Typical content shape**: feed-style entries with timestamps and linked documents.
- **High-value extracted signals**:
  - inflation/labor/growth-related release context
  - macro trend acceleration/deceleration references
  - indicator-specific narrative changes around data prints
- **Operational notes**:
  - structured discovery via RSS-like feeds
  - can generate frequent cadence updates tied to scheduled releases

### SEC EDGAR

- **Primary data type**: public company filings (currently focused on live filing feed variants).
- **Typical content shape**: filing metadata with links to filing pages and exhibits.
- **High-value extracted signals**:
  - corporate actions and governance changes
  - risk-factor, guidance, and liquidity language shifts
  - event-driven disclosures with market implications
- **Operational notes**:
  - heterogeneous filing content and markup quality
  - important for issuer-specific and sector-specific event detection

### GDELT

- **Primary data type**: large-scale global news event exports.
- **Typical content shape**: high-volume batch file updates (zipped export files).
- **High-value extracted signals**:
  - geopolitical and cross-border event pressure
  - supply-chain and conflict-linked narrative movement
  - broad topic momentum and cross-region event clusters
- **Operational notes**:
  - highest ingestion volume among current sources
  - useful for breadth and early weak-signal detection

### Cross-Source Signal Strategy

- **Macro policy lens**: FED + FRED provide policy and release context.
- **Issuer/event lens**: SEC EDGAR contributes company-specific disclosure signals.
- **Global breadth lens**: GDELT contributes broad event coverage and narrative emergence.
- **Fusion outcome**: downstream workers combine event evidence into narratives and scored signals that can trigger alert rules.

## 3. Data Flow

### 3.1 Ingestion

1. Connector discovers source items (FED, FRED, SEC EDGAR, GDELT).
2. Connector fetches content and computes deterministic ingestion identifiers.
3. Raw payload is stored in object storage and persisted in `raw_documents`.
4. Connector publishes `raw.document.ingested` event to Kafka.

Key properties:

- Checkpoint progression is tied to successful publish completion.
- Duplicate raw records are republished downstream to recover from prior partial failures.
- Connector runners require explicit tenant context at execution time.

### 3.2 Normalization

1. Normalizer consumes raw document events.
2. Content is parsed into canonical normalized shape.
3. Deduplication checks run (exact hash and near-duplicate).
4. Canonical/duplicate lineage is persisted in PostgreSQL.
5. Canonical document is indexed in OpenSearch.
6. Normalized and enrichment-request events are published.

Key property:

- Idempotent replay: if a document already exists by deterministic identifier, processing exits early to prevent duplicate downstream side effects.

### 3.3 Enrichment

1. Enrichment worker consumes normalization output.
2. Rule-based extraction creates entities, events, and evidence spans.
3. Deterministic IDs are used for replay-safe writes.
4. Extracted payloads are published for intelligence processing.

### 3.4 Intelligence and Alerts

1. Intelligence worker consumes extracted events.
2. Narrative updates and signal generation run.
3. Alert candidate events are produced.
4. Alert worker evaluates rules and executes channel delivery (email/webhook).

Key properties:

- Tenant ID is required in event payloads for multi-tenant isolation.
- Delivery records use deterministic IDs for idempotent retries.
- Delivery failures are retried and can route through DLQ behavior at consumer boundaries.

## 4. Serving Layer

The API (`apps/api`) provides:

- document/entity/event/narrative/signal access
- alert rule lifecycle management
- hybrid search over indexed data

Current search behavior:

- search is restricted to document index paths that are currently populated
- event/narrative retrieval remains available through domain APIs backed by database repositories

## 5. Security and Policy Controls

- API key authentication with role-based authorization.
- Redis-backed distributed rate limiting.
- Explicit development auth bypass gate (`ALLOW_DEV_AUTH`).
- Licence-aware response filtering before serving text.
- Webhook SSRF safeguards:
  - strict scheme checks
  - hostname allowlist in non-development environments
  - private/link-local/loopback address rejection
  - redirect following disabled in delivery worker

## 6. Reliability and Idempotency Patterns

- Deterministic UUID generation for documents, mentions, events, signals, and deliveries.
- Duplicate-safe persistence checks before inserts.
- Kafka DLQ integration in workers for terminal handler failures.
- Connector checkpoint updates only after successful completion semantics.

## 7. Repository-Level Architecture Map

- `apps/api`: REST API, auth, search, policy-aware response shaping
- `apps/alert-worker`: alert dispatch and channel delivery execution
- `services/connectors/*`: source-specific discovery/fetch logic
- `services/normalizer`: raw-to-canonical parsing, dedup, indexing trigger
- `services/enrichment-worker`: extraction and evidence generation
- `services/intelligence-worker`: narrative/signal generation and alert candidate emission
- `packages/database`: models, sessions, repositories, migrations
- `packages/messaging`: Kafka consumer/producer wrappers and payload contracts
- `packages/source-licensing`: content serving policy enforcement
- `docs/decisions`: architecture decision records (ADRs)

## 8. Cross-References

- ADR-001: Monorepo Structure
- ADR-002: Kafka Event Backbone
- ADR-003: PostgreSQL Operational Store
- ADR-004: Hybrid Search
- ADR-005: Immutable Raw Storage
- ADR-006: Evidence-First Extraction
- ADR-007: Centralized Model Gateway
- ADR-008: Versioned Schemas
- ADR-009: Transparent Signals
- ADR-010: Licence-Aware Serving
