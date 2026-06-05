"""Add quant snapshot metadata

Revision ID: 009
Revises: 008
Create Date: 2026-06-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("odds_snapshots", sa.Column("book", sa.String(64), nullable=True))
    op.add_column("odds_snapshots", sa.Column("event_id", sa.String(128), nullable=True))
    op.add_column(
        "odds_snapshots",
        sa.Column("platform_market_id", sa.String(128), nullable=True),
    )
    op.add_column("odds_snapshots", sa.Column("title", sa.String(256), nullable=True))
    op.add_column(
        "odds_snapshots",
        sa.Column(
            "market_type",
            sa.String(32),
            nullable=False,
            server_default="binary",
        ),
    )
    op.add_column(
        "odds_snapshots",
        sa.Column(
            "outcome_name",
            sa.String(128),
            nullable=False,
            server_default="Yes",
        ),
    )
    op.add_column("odds_snapshots", sa.Column("line", sa.Numeric(10, 4), nullable=True))
    op.add_column("odds_snapshots", sa.Column("price", sa.Numeric(10, 4), nullable=True))
    op.add_column(
        "odds_snapshots",
        sa.Column("close_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "odds_snapshots",
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.execute("UPDATE odds_snapshots SET price = implied_yes WHERE price IS NULL")
    op.alter_column("odds_snapshots", "market_type", server_default=None)
    op.alter_column("odds_snapshots", "outcome_name", server_default=None)
    op.alter_column("odds_snapshots", "metadata", server_default=None)
    op.create_table(
        "signal_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("signal_type", sa.String(32), nullable=False),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("market_id", sa.String(128), nullable=False),
        sa.Column("headline_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.alter_column("signal_events", "headline_eligible", server_default=None)
    op.alter_column("signal_events", "payload", server_default=None)
    op.create_index(
        "ix_signal_events_type_market",
        "signal_events",
        ["signal_type", "platform", "market_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_signal_events_type_market", table_name="signal_events")
    op.drop_table("signal_events")
    op.drop_column("odds_snapshots", "metadata")
    op.drop_column("odds_snapshots", "close_at")
    op.drop_column("odds_snapshots", "price")
    op.drop_column("odds_snapshots", "line")
    op.drop_column("odds_snapshots", "outcome_name")
    op.drop_column("odds_snapshots", "market_type")
    op.drop_column("odds_snapshots", "title")
    op.drop_column("odds_snapshots", "platform_market_id")
    op.drop_column("odds_snapshots", "event_id")
    op.drop_column("odds_snapshots", "book")
