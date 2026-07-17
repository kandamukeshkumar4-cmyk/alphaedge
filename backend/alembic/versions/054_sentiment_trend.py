"""persist market sentiment snapshots (Loop V61 S2).

Revision ID: 054_sentiment_trend
Revises: 053_pods
Create Date: 2026-07-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "054_sentiment_trend"
down_revision: Union[str, Sequence[str], None] = "053_pods"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_sentiment_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("market_slug", sa.String(length=128), nullable=False),
        sa.Column("sentiment_score", sa.Float(), nullable=False),
        sa.Column("volume_score", sa.Float(), nullable=False),
        sa.Column("sources_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="public-news"),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sentiment_market_captured",
        "market_sentiment_snapshots",
        ["market_slug", "captured_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sentiment_market_captured", table_name="market_sentiment_snapshots")
    op.drop_table("market_sentiment_snapshots")
