"""per-user notification preferences (L03) — stored + read in-app only

Revision ID: 036_notify_prefs
Revises: 035_watchlist
Create Date: 2026-07-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "036_notify_prefs"
down_revision: Union[str, Sequence[str], None] = "035_watchlist"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notify_prefs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("families", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id", name="uq_notify_prefs_user"),
    )
    op.create_index("ix_notify_prefs_user_id", "notify_prefs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_notify_prefs_user_id", table_name="notify_prefs")
    op.drop_table("notify_prefs")
