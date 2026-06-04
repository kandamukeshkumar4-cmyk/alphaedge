"""Add AlphaEdge Mirror forecast track-record ledger

Revision ID: 004
Revises: 003
Create Date: 2026-06-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    platform = postgresql.ENUM(
        "polymarket", "kalshi", "manual", name="platform", create_type=True
    )
    external_market_status = postgresql.ENUM(
        "open", "resolved", name="external_market_status", create_type=True
    )
    forecast_mode = postgresql.ENUM("live", "practice", name="forecast_mode", create_type=True)
    forecast_source = postgresql.ENUM(
        "extension", "web", "backfill", name="forecast_source", create_type=True
    )

    op.create_table(
        "forecasters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("recovery_email_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_forecasters_token_hash", "forecasters", ["token_hash"], unique=True)
    op.create_index("ix_forecasters_recovery_email_hash", "forecasters", ["recovery_email_hash"])

    op.create_table(
        "external_markets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", platform, nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("url", sa.String(512), nullable=False, server_default=""),
        sa.Column("title", sa.String(256), nullable=False, server_default=""),
        sa.Column("category", sa.String(64), nullable=False, server_default="Uncategorized"),
        sa.Column("status", external_market_status, nullable=False, server_default="open"),
        sa.Column("close_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("winning_outcome", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_external_markets_platform_external_id",
        "external_markets",
        ["platform", "external_id"],
        unique=True,
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
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_market_snapshots_market_captured",
        "market_snapshots",
        ["external_market_id", "captured_at"],
    )

    op.create_table(
        "forecast_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "forecaster_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forecasters.id"),
            nullable=False,
        ),
        sa.Column(
            "external_market_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("external_markets.id"),
            nullable=False,
        ),
        sa.Column(
            "market_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("market_snapshots.id"),
            nullable=True,
        ),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("platform", platform, nullable=False),
        sa.Column("market_url", sa.String(512), nullable=False, server_default=""),
        sa.Column("outcome_label", sa.String(128), nullable=False, server_default="YES"),
        sa.Column("user_probability", sa.Numeric(6, 4), nullable=False),
        sa.Column("market_implied_probability", sa.Numeric(6, 4), nullable=True),
        sa.Column("snapshot_source", sa.String(64), nullable=False, server_default="manual"),
        sa.Column("is_independent", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("mode", forecast_mode, nullable=False, server_default="live"),
        sa.Column("source", forecast_source, nullable=False, server_default="web"),
        sa.Column("snapshot_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("time_to_resolution_seconds", sa.Integer(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_forecast_logs_forecaster_market_seq",
        "forecast_logs",
        ["forecaster_id", "external_market_id", "seq"],
        unique=True,
    )
    op.create_index("ix_forecast_logs_market", "forecast_logs", ["external_market_id"])

    op.create_table(
        "forecast_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "forecast_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forecast_logs.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("actual_outcome", sa.Integer(), nullable=False),
        sa.Column("user_brier", sa.Numeric(8, 6), nullable=False),
        sa.Column("market_brier", sa.Numeric(8, 6), nullable=True),
        sa.Column("brier_delta", sa.Numeric(8, 6), nullable=True),
        sa.Column("synthetic_pnl", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("scored_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("forecast_scores")
    op.drop_index("ix_forecast_logs_market", table_name="forecast_logs")
    op.drop_index("ix_forecast_logs_forecaster_market_seq", table_name="forecast_logs")
    op.drop_table("forecast_logs")
    op.drop_index("ix_market_snapshots_market_captured", table_name="market_snapshots")
    op.drop_table("market_snapshots")
    op.drop_index("ix_external_markets_platform_external_id", table_name="external_markets")
    op.drop_table("external_markets")
    op.drop_index("ix_forecasters_recovery_email_hash", table_name="forecasters")
    op.drop_index("ix_forecasters_token_hash", table_name="forecasters")
    op.drop_table("forecasters")

    for enum_name in ("forecast_source", "forecast_mode", "external_market_status", "platform"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
