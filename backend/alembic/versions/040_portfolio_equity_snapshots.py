"""add portfolio equity snapshots for equity curve (B5)

Revision ID: 040_portfolio_equity_snapshots
Revises: 039_order_expiry
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "040_portfolio_equity_snapshots"
down_revision: Union[str, Sequence[str], None] = "039_order_expiry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_equity_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("cash_balance", sa.Numeric(18, 4), nullable=False),
        sa.Column("positions_mtm", sa.Numeric(18, 4), nullable=False),
        sa.Column("equity", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "snapshot_date", name="uq_portfolio_equity_user_date"
        ),
    )
    op.create_index(
        "ix_portfolio_equity_snapshots_user_id",
        "portfolio_equity_snapshots",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portfolio_equity_snapshots_user_id",
        table_name="portfolio_equity_snapshots",
    )
    op.drop_table("portfolio_equity_snapshots")
