"""Migration 004: add alert rule delivery config."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_alert_rule_delivery_config"
down_revision: str | None = "003_document_sentiment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "alert_rules",
        sa.Column(
            "delivery_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column("alert_rules", "delivery_config", server_default=None)


def downgrade() -> None:
    op.drop_column("alert_rules", "delivery_config")
