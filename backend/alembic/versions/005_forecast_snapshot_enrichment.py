"""Add forecast snapshot enrichment

Revision ID: 005
Revises: 004
Create Date: 2026-06-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    platform = postgresql.ENUM(
        "polymarket", "kalshi", "manual", name="platform", create_type=False
    )

    op.create_table(
        "market_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "external_market_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("external_markets.id"),
            nullable=False,
        ),
        sa.Column("platform", platform, nullable=False),
        sa.Column("implied_probability", sa.Numeric(6, 4), nullable=True),
        sa.Column("source", sa.String(64), nullable=False, server_default="manual"),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_market_snapshots_market_captured",
        "market_snapshots",
        ["external_market_id", "captured_at"],
    )

    op.add_column(
        "forecast_logs",
        sa.Column(
            "market_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("market_snapshots.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "forecast_logs",
        sa.Column("platform", platform, nullable=False, server_default="manual"),
    )
    op.add_column(
        "forecast_logs",
        sa.Column("market_url", sa.String(512), nullable=False, server_default=""),
    )
    op.add_column(
        "forecast_logs",
        sa.Column("outcome_label", sa.String(128), nullable=False, server_default="YES"),
    )
    op.add_column(
        "forecast_logs",
        sa.Column(
            "snapshot_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )

    op.execute(
        """
        UPDATE forecast_logs
        SET
            platform = external_markets.platform,
            market_url = external_markets.url
        FROM external_markets
        WHERE forecast_logs.external_market_id = external_markets.id
        """
    )
    op.alter_column("forecast_logs", "platform", server_default=None)


def downgrade() -> None:
    op.drop_column("forecast_logs", "snapshot_metadata")
    op.drop_column("forecast_logs", "outcome_label")
    op.drop_column("forecast_logs", "market_url")
    op.drop_column("forecast_logs", "platform")
    op.drop_column("forecast_logs", "market_snapshot_id")
    op.drop_index("ix_market_snapshots_market_captured", table_name="market_snapshots")
    op.drop_table("market_snapshots")
