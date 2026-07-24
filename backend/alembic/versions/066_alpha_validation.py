"""persist point-in-time alpha validation inputs

Revision ID: 066_alpha_validation
Revises: 065_social_community
Create Date: 2026-07-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "066_alpha_validation"
down_revision: Union[str, Sequence[str], None] = "065_social_community"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alpha_factor_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("forecast_id", sa.Uuid(), nullable=False),
        sa.Column("external_market_id", sa.Uuid(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("factor_values", sa.JSON(), nullable=False),
        sa.Column("factor_provenance", sa.JSON(), nullable=False),
        sa.Column("capture_version", sa.String(length=32), nullable=False),
        sa.Column(
            "backfilled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["external_market_id"],
            ["external_markets.id"],
        ),
        sa.ForeignKeyConstraint(["forecast_id"], ["forecast_logs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("forecast_id"),
    )
    op.create_index(
        "ix_alpha_factor_market_observed",
        "alpha_factor_snapshots",
        ["external_market_id", "observed_at"],
        unique=False,
    )
    op.create_table(
        "alpha_closing_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("forecast_id", sa.Uuid(), nullable=False),
        sa.Column("external_market_id", sa.Uuid(), nullable=False),
        sa.Column("source_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column(
            "closing_implied_probability",
            sa.Numeric(precision=6, scale=4),
            nullable=False,
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cutoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column(
            "is_estimate",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "backfilled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["external_market_id"],
            ["external_markets.id"],
        ),
        sa.ForeignKeyConstraint(["forecast_id"], ["forecast_logs.id"]),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"],
            ["odds_snapshots.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("forecast_id"),
    )
    op.create_index(
        "ix_alpha_closing_market_observed",
        "alpha_closing_lines",
        ["external_market_id", "observed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_alpha_closing_market_observed",
        table_name="alpha_closing_lines",
    )
    op.drop_table("alpha_closing_lines")
    op.drop_index(
        "ix_alpha_factor_market_observed",
        table_name="alpha_factor_snapshots",
    )
    op.drop_table("alpha_factor_snapshots")
