"""paper_orders sell/close columns

Revision ID: 021_paper_order_sell_close
Revises: 020_mirror_dashboard_indexes
Create Date: 2026-06-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "021_paper_order_sell_close"
down_revision: Union[str, Sequence[str], None] = "020_mirror_dashboard_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "paper_orders",
        sa.Column("action", sa.String(length=4), nullable=False, server_default="BUY"),
    )
    op.add_column(
        "paper_orders",
        sa.Column("realized_pnl", sa.Numeric(18, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("paper_orders", "realized_pnl")
    op.drop_column("paper_orders", "action")
