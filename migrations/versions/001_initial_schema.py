"""Initial schema migration."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "sources",
        sa.Column("source_id", sa.String(64), primary_key=True),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("jurisdiction", sa.String(8)),
        sa.Column("homepage_url", sa.String(512)),
        sa.Column("credibility_score", sa.Float, server_default="0.5"),
        sa.Column("licence_type", sa.String(64), nullable=False),
        sa.Column("redistribution_allowed", sa.Boolean, server_default="true"),
        sa.Column("commercial_use_allowed", sa.Boolean, server_default="true"),
        sa.Column("active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "tenants",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("sources.source_id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(32), server_default="running"),
        sa.Column("items_discovered", sa.Integer, server_default="0"),
        sa.Column("items_ingested", sa.Integer, server_default="0"),
        sa.Column("items_failed", sa.Integer, server_default="0"),
        sa.Column("checkpoint", postgresql.JSONB),
    )

    op.create_table(
        "raw_documents",
        sa.Column("ingestion_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("sources.source_id"), nullable=False),
        sa.Column("external_id", sa.String(255)),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("object_store_uri", sa.String(1024), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False, index=True),
        sa.Column("connector_version", sa.String(32), nullable=False),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
    )

    op.create_table(
        "canonical_documents",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("sources.source_id"), nullable=False),
        sa.Column("external_id", sa.String(255)),
        sa.Column("canonical_url", sa.String(2048), nullable=False),
        sa.Column("title", sa.String(1024)),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("language", sa.String(8), server_default="en"),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_type", sa.String(64), server_default="article"),
        sa.Column("country_codes", postgresql.JSONB, server_default="[]"),
        sa.Column("topic_labels", postgresql.JSONB, server_default="[]"),
        sa.Column("content_hash", sa.String(64), nullable=False, index=True),
        sa.Column("parser_version", sa.String(32), nullable=False),
        sa.Column("source_record_id", sa.String(64), nullable=False),
        sa.Column("is_canonical", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "document_duplicates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "canonical_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_documents.document_id"),
            nullable=False,
        ),
        sa.Column(
            "duplicate_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_documents.document_id"),
            nullable=False,
        ),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
    )

    op.create_table(
        "entities",
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_name", sa.String(512), nullable=False, index=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("country_codes", postgresql.JSONB, server_default="[]"),
        sa.Column("external_ids", postgresql.JSONB, server_default="{}"),
        sa.Column("attributes", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "entity_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.entity_id"),
            nullable=False,
        ),
        sa.Column("alias", sa.String(512), nullable=False, index=True),
    )

    op.create_table(
        "entity_mentions",
        sa.Column("mention_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_documents.document_id"),
            nullable=False,
        ),
        sa.Column("text", sa.String(512), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("start_offset", sa.Integer, nullable=False),
        sa.Column("end_offset", sa.Integer, nullable=False),
        sa.Column(
            "canonical_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.entity_id"),
        ),
        sa.Column("extraction_confidence", sa.Float, nullable=False),
        sa.Column("linking_confidence", sa.Float),
        sa.Column("model_version", sa.String(32), nullable=False),
    )

    op.create_table(
        "events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_documents.document_id"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(128), nullable=False, index=True),
        sa.Column("action", sa.String(256), nullable=False),
        sa.Column("object_name", sa.String(512)),
        sa.Column("magnitude", sa.Float),
        sa.Column("unit", sa.String(64)),
        sa.Column("event_time", sa.DateTime(timezone=True)),
        sa.Column("effective_time", sa.DateTime(timezone=True)),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("extraction_model_version", sa.String(32), nullable=False),
        sa.Column("prompt_version", sa.String(32)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "evidence_spans",
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_documents.document_id"),
            nullable=False,
        ),
        sa.Column("start_offset", sa.Integer, nullable=False),
        sa.Column("end_offset", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("model_version", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
    )

    op.create_table(
        "event_evidence",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.event_id"),
            primary_key=True,
        ),
        sa.Column(
            "evidence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence_spans.evidence_id"),
            primary_key=True,
        ),
    )

    op.create_table(
        "narratives",
        sa.Column("narrative_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("lifecycle_state", sa.String(32), nullable=False),
        sa.Column("topic_labels", postgresql.JSONB, server_default="[]"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("velocity_score", sa.Float, server_default="0"),
        sa.Column("novelty_score", sa.Float, server_default="0"),
        sa.Column("source_diversity_score", sa.Float, server_default="0"),
        sa.Column("market_relevance_score", sa.Float, server_default="0"),
        sa.Column("sentiment_score", sa.Float, server_default="0"),
        sa.Column("clustering_version", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "narrative_events",
        sa.Column(
            "narrative_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("narratives.narrative_id"),
            primary_key=True,
        ),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.event_id"),
            primary_key=True,
        ),
    )

    op.create_table(
        "signals",
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("signal_type", sa.String(128), nullable=False, index=True),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entities.entity_id"),
        ),
        sa.Column("asset_id", sa.String(64)),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("horizon", sa.String(32), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("calculation_version", sa.String(32), nullable=False),
        sa.Column("component_scores", postgresql.JSONB, server_default="{}"),
    )

    op.create_table(
        "signal_evidence",
        sa.Column(
            "signal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("signals.signal_id"),
            primary_key=True,
        ),
        sa.Column(
            "evidence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence_spans.evidence_id"),
            primary_key=True,
        ),
    )

    op.create_table(
        "users",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.tenant_id"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("role", sa.String(32), server_default="viewer"),
        sa.Column("active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "api_keys",
        sa.Column("key_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.tenant_id"),
            nullable=False,
        ),
        sa.Column("key_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), server_default="api_client"),
        sa.Column("active", sa.Boolean, server_default="true"),
        sa.Column("rate_limit", sa.Integer, server_default="1000"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "alert_rules",
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.tenant_id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("entity_ids", postgresql.JSONB, server_default="[]"),
        sa.Column("topic_labels", postgresql.JSONB, server_default="[]"),
        sa.Column("event_types", postgresql.JSONB, server_default="[]"),
        sa.Column("signal_types", postgresql.JSONB, server_default="[]"),
        sa.Column("minimum_confidence", sa.Float, server_default="0.5"),
        sa.Column("minimum_score", sa.Float, server_default="0.5"),
        sa.Column("countries", postgresql.JSONB, server_default="[]"),
        sa.Column("delivery_channels", postgresql.JSONB, server_default="[]"),
        sa.Column("cooldown_period_seconds", sa.Integer, server_default="3600"),
        sa.Column("active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "alert_deliveries",
        sa.Column("delivery_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "alert_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alert_rules.alert_id"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("payload", postgresql.JSONB, server_default="{}"),
        sa.Column("error_message", sa.Text),
    )

    op.create_table(
        "model_versions",
        sa.Column("version_id", sa.String(64), primary_key=True),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("deployed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
    )

    op.create_table(
        "audit_log",
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True)),
        sa.Column("user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(128)),
        sa.Column("details", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    tables = [
        "audit_log",
        "model_versions",
        "alert_deliveries",
        "alert_rules",
        "api_keys",
        "users",
        "signal_evidence",
        "signals",
        "narrative_events",
        "narratives",
        "event_evidence",
        "evidence_spans",
        "events",
        "entity_mentions",
        "entity_aliases",
        "entities",
        "document_duplicates",
        "canonical_documents",
        "raw_documents",
        "ingestion_runs",
        "tenants",
        "sources",
    ]
    for table in tables:
        op.drop_table(table)
    op.execute("DROP EXTENSION IF EXISTS vector")
