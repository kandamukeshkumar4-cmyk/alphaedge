"""require a lock timestamp for live forecasts

Revision ID: 055_live_forecast_lock
Revises: 054_sentiment_trend
Create Date: 2026-07-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "055_live_forecast_lock"
down_revision: Union[str, Sequence[str], None] = "054_sentiment_trend"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_live_forecast_locked",
        "forecast_logs",
        "mode != 'live' OR locked_at IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_live_forecast_locked", "forecast_logs", type_="check")
