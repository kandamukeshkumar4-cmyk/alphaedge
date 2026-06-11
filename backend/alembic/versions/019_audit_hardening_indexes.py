"""audit hardening indexes

Revision ID: 019_audit_hardening_indexes
Revises: 018_wc2026_tag
Create Date: 2026-06-11
"""

from typing import Sequence, Union

from alembic import op

revision: str = "019_audit_hardening_indexes"
down_revision: Union[str, Sequence[str], None] = "018_wc2026_tag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_odds_snapshots_market_source_captured",
        "odds_snapshots",
        ["market_slug", "source", "captured_at"],
    )
    op.create_index(
        "ix_forecast_logs_forecaster_id",
        "forecast_logs",
        ["forecaster_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_forecast_logs_forecaster_id", table_name="forecast_logs")
    op.drop_index(
        "ix_odds_snapshots_market_source_captured",
        table_name="odds_snapshots",
    )
