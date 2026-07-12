"""Migration 003: document sentiment scores."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_document_sentiment"
down_revision: str | None = "002_document_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_sentiment",
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_documents.document_id"),
            primary_key=True,
        ),
        sa.Column("model_version", sa.String(32), nullable=False),
        sa.Column("scores", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_document_sentiment_model", "document_sentiment", ["model_version"])


def downgrade() -> None:
    op.drop_table("document_sentiment")
