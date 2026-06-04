"""Add forecast lock idempotency keys

Revision ID: 006
Revises: 005
Create Date: 2026-06-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("forecast_logs", sa.Column("idempotency_key", sa.String(128), nullable=True))
    op.create_index(
        "ix_forecast_logs_forecaster_idempotency",
        "forecast_logs",
        ["forecaster_id", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_forecast_logs_forecaster_idempotency", table_name="forecast_logs")
    op.drop_column("forecast_logs", "idempotency_key")
