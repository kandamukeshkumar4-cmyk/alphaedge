"""paper_orders table for JWT user paper trades

Revision ID: 012_paper_orders
Revises: 011_users
Create Date: 2026-06-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012_paper_orders"
down_revision: Union[str, None] = "011_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("side", sa.String(length=3), nullable=False),
        sa.Column("shares", sa.Numeric(18, 4), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=False),
        sa.Column("cost", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_paper_orders_user_id", "paper_orders", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_paper_orders_user_id", table_name="paper_orders")
    op.drop_table("paper_orders")
