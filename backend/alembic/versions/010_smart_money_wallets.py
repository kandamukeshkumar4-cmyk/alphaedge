"""Add smart-money wallet tracking

Revision ID: 010
Revises: 009
Create Date: 2026-06-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tracked_wallets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wallet_address", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False, server_default=""),
        sa.Column("realized_pnl", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("unrealized_pnl", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("roi", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("hit_rate", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("total_trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("qualified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tracked_wallets_wallet_address",
        "tracked_wallets",
        ["wallet_address"],
        unique=True,
    )
    op.create_index(
        "ix_tracked_wallets_qualified_roi",
        "tracked_wallets",
        ["qualified", "roi"],
    )
    op.alter_column("tracked_wallets", "label", server_default=None)
    op.alter_column("tracked_wallets", "realized_pnl", server_default=None)
    op.alter_column("tracked_wallets", "unrealized_pnl", server_default=None)
    op.alter_column("tracked_wallets", "roi", server_default=None)
    op.alter_column("tracked_wallets", "hit_rate", server_default=None)
    op.alter_column("tracked_wallets", "total_trades", server_default=None)
    op.alter_column("tracked_wallets", "qualified", server_default=None)
    op.alter_column("tracked_wallets", "metadata", server_default=None)

    op.create_table(
        "wallet_positions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tracked_wallet_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("market_id", sa.String(128), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("side", sa.String(32), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("average_price", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("current_price", sa.Numeric(10, 4), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("unrealized_pnl", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_pnl", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tracked_wallet_id"], ["tracked_wallets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wallet_positions_market", "wallet_positions", ["platform", "market_id"])
    op.create_index(
        "ix_wallet_positions_wallet_market",
        "wallet_positions",
        ["tracked_wallet_id", "platform", "market_id"],
    )
    op.alter_column("wallet_positions", "quantity", server_default=None)
    op.alter_column("wallet_positions", "average_price", server_default=None)
    op.alter_column("wallet_positions", "realized_pnl", server_default=None)
    op.alter_column("wallet_positions", "unrealized_pnl", server_default=None)
    op.alter_column("wallet_positions", "total_pnl", server_default=None)
    op.alter_column("wallet_positions", "metadata", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_wallet_positions_wallet_market", table_name="wallet_positions")
    op.drop_index("ix_wallet_positions_market", table_name="wallet_positions")
    op.drop_table("wallet_positions")
    op.drop_index("ix_tracked_wallets_qualified_roi", table_name="tracked_wallets")
    op.drop_index("ix_tracked_wallets_wallet_address", table_name="tracked_wallets")
    op.drop_table("tracked_wallets")
