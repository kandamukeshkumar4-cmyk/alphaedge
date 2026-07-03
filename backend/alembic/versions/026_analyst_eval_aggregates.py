"""analyst_eval_aggregates (T08 public track record)

Revision ID: 026_analyst_eval_aggregates
Revises: 025_analyst_briefs
Create Date: 2026-07-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "026_analyst_eval_aggregates"
down_revision: Union[str, Sequence[str], None] = "025_analyst_briefs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analyst_eval_aggregates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dimension", sa.String(length=32), nullable=False),
        sa.Column("dim_key", sa.String(length=64), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("n", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accuracy", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("brier", sa.Numeric(8, 6), nullable=False, server_default="0"),
        sa.Column("provisional", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_analyst_eval_dimension_key_window",
        "analyst_eval_aggregates",
        ["dimension", "dim_key", "window_days"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_analyst_eval_dimension_key_window", table_name="analyst_eval_aggregates"
    )
    op.drop_table("analyst_eval_aggregates")
