"""O05 weather_forecast_logs — NWS forecast highs + sigma used per city/day,
so observed highs can be filled in later and forecast-vs-actual sigma learned.

Revision ID: 031_weather_forecast_logs
Revises: 030_backtest_runs
Create Date: 2026-07-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "031_weather_forecast_logs"
down_revision: Union[str, Sequence[str], None] = "030_backtest_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "weather_forecast_logs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("city", sa.String(64), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("forecast_high_f", sa.Numeric(6, 2), nullable=False),
        sa.Column("sigma_used", sa.Numeric(6, 3), nullable=False),
        sa.Column("actual_high_f", sa.Numeric(6, 2), nullable=True),
        sa.Column(
            "source", sa.String(64), nullable=False, server_default="nws.point-forecast"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("city", "target_date", name="uq_weather_forecast_city_date"),
    )
    op.create_index(
        "ix_weather_forecast_target_date", "weather_forecast_logs", ["target_date"]
    )


def downgrade() -> None:
    op.drop_table("weather_forecast_logs")
