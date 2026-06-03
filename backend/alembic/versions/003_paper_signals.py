"""Add persisted paper trader signals

Revision ID: 003
Revises: 002
Create Date: 2026-06-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    order_outcome = postgresql.ENUM("yes", "no", name="order_outcome", create_type=False)
    op.create_table(
        "paper_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("outcome", order_outcome, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_paper_signals_account_market",
        "paper_signals",
        ["account_id", "market_id"],
        unique=True,
    )
    op.create_index(
        "ix_paper_signals_market_outcome",
        "paper_signals",
        ["market_id", "outcome"],
    )


def downgrade() -> None:
    op.drop_index("ix_paper_signals_market_outcome", table_name="paper_signals")
    op.drop_index("ix_paper_signals_account_market", table_name="paper_signals")
    op.drop_table("paper_signals")
