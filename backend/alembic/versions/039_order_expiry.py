"""add GTD expiry to CLOB orders

Revision ID: 039_order_expiry
Revises: 038_clob_order_idempotency
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "039_order_expiry"
down_revision: Union[str, Sequence[str], None] = "038_clob_order_idempotency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_orders_status_expires_at",
        "orders",
        ["status", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_orders_status_expires_at", table_name="orders")
    op.drop_column("orders", "expires_at")
