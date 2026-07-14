"""forecast drift snapshots (D2)

Revision ID: 042_forecast_drift_snapshots
Revises: 041_model_registry_active
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "042_forecast_drift_snapshots"
down_revision: Union[str, Sequence[str], None] = "041_model_registry_active"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "forecast_drift_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("window_n", sa.Integer(), nullable=False),
        sa.Column("rolling_brier", sa.Float(), nullable=True),
        sa.Column("rolling_ece", sa.Float(), nullable=True),
        sa.Column("baseline_brier", sa.Float(), nullable=False),
        sa.Column("baseline_ece", sa.Float(), nullable=False),
        sa.Column("brier_delta", sa.Float(), nullable=True),
        sa.Column("ece_delta", sa.Float(), nullable=True),
        sa.Column(
            "degraded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_forecast_drift_snapshots_computed_at",
        "forecast_drift_snapshots",
        ["computed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_forecast_drift_snapshots_computed_at",
        table_name="forecast_drift_snapshots",
    )
    op.drop_table("forecast_drift_snapshots")
