"""paper_orders idempotency key — dedupe retried POST /api/v1/orders (audit C-RACE-01/H-RACE-01)

Revision ID: 037_paper_order_idempotency
Revises: 036_notify_prefs
Create Date: 2026-07-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "037_paper_order_idempotency"
down_revision: Union[str, Sequence[str], None] = "036_notify_prefs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("paper_orders", sa.Column("idempotency_key", sa.String(64), nullable=True))
    op.create_unique_constraint(
        "uq_paper_orders_user_idem", "paper_orders", ["user_id", "idempotency_key"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_paper_orders_user_idem", "paper_orders", type_="unique")
    op.drop_column("paper_orders", "idempotency_key")
