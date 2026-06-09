"""paper_orders.outcome column

Revision ID: 014_paper_order_outcome
Revises: 013_market_resolutions
Create Date: 2026-06-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014_paper_order_outcome"
down_revision: Union[str, None] = "013_market_resolutions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "paper_orders",
        sa.Column("outcome", sa.String(length=3), nullable=False, server_default="yes"),
    )
    op.execute(
        """
        UPDATE paper_orders
        SET outcome = LOWER(side)
        WHERE side IN ('YES', 'NO')
        """
    )


def downgrade() -> None:
    op.drop_column("paper_orders", "outcome")
