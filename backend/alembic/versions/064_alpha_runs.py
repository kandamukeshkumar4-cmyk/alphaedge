"""persist multi-factor alpha research runs

Revision ID: 064_alpha_runs
Revises: 063_marketplace_ratings
Create Date: 2026-07-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "064_alpha_runs"
down_revision: Union[str, Sequence[str], None] = "063_marketplace_ratings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alpha_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("rejection_reasons", sa.JSON(), nullable=False),
        sa.Column("paper_trading_only", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_date"),
    )
    op.create_index("ix_alpha_runs_created_at", "alpha_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_alpha_runs_created_at", table_name="alpha_runs")
    op.drop_table("alpha_runs")
