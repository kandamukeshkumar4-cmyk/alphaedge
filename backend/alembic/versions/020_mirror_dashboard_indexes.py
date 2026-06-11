"""mirror dashboard indexes

Revision ID: 020_mirror_dashboard_indexes
Revises: 019_audit_hardening_indexes
Create Date: 2026-06-11
"""

from typing import Sequence, Union

from alembic import op

revision: str = "020_mirror_dashboard_indexes"
down_revision: Union[str, Sequence[str], None] = "019_audit_hardening_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_external_markets_status", "external_markets", ["status"])
    op.create_index(
        "ix_forecast_logs_forecaster_locked",
        "forecast_logs",
        ["forecaster_id", "locked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_forecast_logs_forecaster_locked", table_name="forecast_logs")
    op.drop_index("ix_external_markets_status", table_name="external_markets")
