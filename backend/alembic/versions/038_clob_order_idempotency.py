"""orders idempotency key — dedupe retried CLOB submissions (audit M-RACE-01)

Revision ID: 038_clob_order_idempotency
Revises: 037_paper_order_idempotency
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "038_clob_order_idempotency"
down_revision: Union[str, Sequence[str], None] = "037_paper_order_idempotency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("idempotency_key", sa.String(64), nullable=True))
    op.create_unique_constraint(
        "uq_orders_account_idem", "orders", ["account_id", "idempotency_key"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_orders_account_idem", "orders", type_="unique")
    op.drop_column("orders", "idempotency_key")
