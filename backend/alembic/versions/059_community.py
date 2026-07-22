"""add community subscriptions table

Revision ID: 059_community
Revises: 058_scanners
Create Date: 2026-07-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "059_community"
down_revision: Union[str, Sequence[str], None] = "058_scanners"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user", sa.String(length=64), nullable=False),
        sa.Column("ref_type", sa.String(length=8), nullable=False),
        sa.Column("ref_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user", "ref_type", "ref_id", name="uq_subscriptions_user_ref"),
    )
    op.create_index("ix_subscriptions_user", "subscriptions", ["user"])


def downgrade() -> None:
    op.drop_index("ix_subscriptions_user", table_name="subscriptions")
    op.drop_table("subscriptions")
