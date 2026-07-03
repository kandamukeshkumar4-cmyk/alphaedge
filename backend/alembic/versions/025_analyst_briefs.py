"""analyst_briefs + brief_claims (T07 analyst agent)

Revision ID: 025_analyst_briefs
Revises: 024_wallet_position_snapshots
Create Date: 2026-07-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "025_analyst_briefs"
down_revision: Union[str, Sequence[str], None] = "024_wallet_position_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analyst_briefs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("market_slug", sa.String(length=128), nullable=False),
        sa.Column("trigger_event_id", sa.String(length=64), nullable=True),
        sa.Column("headline", sa.String(length=160), nullable=False),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("model_version", sa.String(length=64), nullable=False, server_default="unknown"),
        sa.Column("prompt_version", sa.String(length=32), nullable=False, server_default="v1"),
        sa.Column("generator", sa.String(length=16), nullable=False, server_default="llm"),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="brief"),
        sa.Column("latency_ms", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_analyst_briefs_market_created", "analyst_briefs", ["market_slug", "created_at"]
    )
    op.create_table(
        "brief_claims",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("brief_id", sa.Uuid(), sa.ForeignKey("analyst_briefs.id"), nullable=False),
        sa.Column("market_slug", sa.String(length=128), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("horizon_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("confidence", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("price_at_claim", sa.Numeric(10, 4), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("resolution_price", sa.Numeric(10, 4), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_brief_claims_status_horizon", "brief_claims", ["status", "horizon_minutes"]
    )


def downgrade() -> None:
    op.drop_index("ix_brief_claims_status_horizon", table_name="brief_claims")
    op.drop_table("brief_claims")
    op.drop_index("ix_analyst_briefs_market_created", table_name="analyst_briefs")
    op.drop_table("analyst_briefs")
