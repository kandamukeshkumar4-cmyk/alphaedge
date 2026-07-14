"""public trader profiles and follow relationships (Loop V22 S1/S2)

Revision ID: 047_social
Revises: 043_signal_events_created_idx
Create Date: 2026-07-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "047_social"
down_revision: Union[str, Sequence[str], None] = "046_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("profile_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_table(
        "follows",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("follower_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("followee_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("follower_id <> followee_id", name="ck_follows_no_self"),
        sa.ForeignKeyConstraint(["follower_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["followee_id"], ["users.id"]),
        sa.UniqueConstraint("follower_id", "followee_id", name="uq_follows_follower_followee"),
    )
    op.create_index("ix_follows_follower_id", "follows", ["follower_id"])
    op.create_index("ix_follows_followee_id", "follows", ["followee_id"])


def downgrade() -> None:
    op.drop_index("ix_follows_followee_id", table_name="follows")
    op.drop_index("ix_follows_follower_id", table_name="follows")
    op.drop_table("follows")
    op.drop_column("users", "profile_public")
