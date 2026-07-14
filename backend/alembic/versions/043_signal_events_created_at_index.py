"""signal_events.created_at index for feed ORDER BY (Loop V21 P1)

Revision ID: 043_signal_events_created_at_index
Revises: 042_forecast_drift_snapshots
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op

revision: str = "043_signal_events_created_at_index"
down_revision: Union[str, Sequence[str], None] = "042_forecast_drift_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_signal_events_created_at",
        "signal_events",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_signal_events_created_at", table_name="signal_events")
