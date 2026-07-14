"""Loop V23: market_status cancelled + users.is_suspended

Revision ID: 045_admin_cancel_suspend
Revises: 043_signal_events_created_idx
Create Date: 2026-07-14

Pre-assigned migration 045 (head was 043; 044 reserved for peer loop V22).
Adds CANCELLED to market_status enum and is_suspended on users for admin ops.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "045_admin_cancel_suspend"
down_revision: Union[str, Sequence[str], None] = "043_signal_events_created_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres enum: ADD VALUE is transactional on PG 12+.
    # IF NOT EXISTS keeps re-runs safe when enum already extended.
    op.execute("ALTER TYPE market_status ADD VALUE IF NOT EXISTS 'cancelled'")
    op.add_column(
        "users",
        sa.Column(
            "is_suspended",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_suspended")
    # Postgres cannot remove enum values safely; leave market_status.cancelled.
