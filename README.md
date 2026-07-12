# Market Intelligence Platform

A production-ready market intelligence platform that ingests public economic, corporate, geopolitical, energy, weather, and news data; normalizes and enriches it; extracts entities and events; detects narratives; generates explainable signals; and serves results through APIs, dashboards, alerts, and search.

## Architecture

```
Public Data Sources → Connectors → Kafka → Processing Pipeline → Storage → API/Dashboard
```

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker and Docker Compose
- Node.js 20+ (for dashboard development)

### Setup

```bash
# Install dependencies
make install

# Start local infrastructure (PostgreSQL, Kafka, Redis, MinIO, OpenSearch, ClickHouse, MLflow)
make dev-up

# Run database migrations
make migrate

# Seed sample data (demonstrates end-to-end Fed inflation narrative + signal)
make seed

# Run tests
make test
```

### Services

| Service | URL | Description |
|---------|-----|-------------|
| API | http://localhost:8000 | REST API with OpenAPI docs at `/docs` |
| Dashboard | http://localhost:3000 | Analyst web interface |
| Model Gateway | http://localhost:8001 | Centralized LLM/embedding access |
| MinIO Console | http://localhost:9001 | Object storage (minioadmin/minioadmin) |
| MLflow | http://localhost:5000 | Experiment tracking |

### API Endpoints

- `GET /health`, `GET /ready`, `GET /metrics` — Platform health
- `GET /v1/documents`, `GET /v1/documents/{id}`, `GET /v1/documents/{id}/evidence`
- `GET /v1/events`, `GET /v1/events/{id}`
- `GET /v1/entities`, `GET /v1/entities/{id}`
- `GET /v1/narratives`, `GET /v1/narratives/{id}`
- `GET /v1/signals`, `GET /v1/signals/{id}`
- `POST /v1/search` — Hybrid document search
- `POST/GET/PATCH/DELETE /v1/alerts` — Alert rules

### Running the Fed Connector

```bash
uv run python -m mip_connector_fed.runner
```

### Environment Variables

Copy `.env.example` to `.env` and adjust as needed. See [Configuration Conventions](docs/architecture/configuration.md).

## Repository Structure

```
├── apps/           # API, dashboard, alert-worker, admin-cli
├── services/       # Connectors, normalizer, NLP, signal engine, model-gateway
├── packages/       # Shared schemas, database, messaging, observability
├── workflows/      # Dagster orchestration (scheduled jobs)
├── infra/          # Terraform, Kubernetes, Docker
├── migrations/     # Alembic database migrations
├── tests/          # Unit, contract, integration, e2e tests
└── docs/           # Architecture, API docs, ADRs, runbooks
```

## Development Commands

```bash
make install      # Install all dependencies
make dev-up       # Start Docker Compose stack
make dev-down     # Stop stack
make migrate      # Run database migrations
make seed         # Load sample data
make test         # Run unit tests
make lint         # Run ruff linter
make typecheck    # Run mypy
make format       # Auto-format code
make e2e          # Run end-to-end tests
```

## Design Principles

1. Raw source data is immutable
2. Every derived output links back to evidence
3. LLMs are enrichment tools, not the system of record
4. All consumers are idempotent
5. Every model output is versioned
6. Structured outputs are schema-validated

## License

See individual source licence metadata for redistribution terms.
