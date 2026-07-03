"""wallet_position_snapshots time-series (T05 whale delta diffing)

Revision ID: 024_wallet_position_snapshots
Revises: 023_market_clob_token_id
Create Date: 2026-07-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "024_wallet_position_snapshots"
down_revision: Union[str, Sequence[str], None] = "023_market_clob_token_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wallet_position_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("wallet_address", sa.String(length=64), nullable=False),
        sa.Column("market_slug", sa.String(length=128), nullable=False),
        sa.Column("outcome", sa.String(length=8), nullable=False, server_default="YES"),
        sa.Column("size", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("avg_price", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_wallet_position_snapshots_wallet_address",
        "wallet_position_snapshots",
        ["wallet_address"],
    )
    op.create_index(
        "ix_wallet_pos_snap_wallet_market_captured",
        "wallet_position_snapshots",
        ["wallet_address", "market_slug", "captured_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_wallet_pos_snap_wallet_market_captured",
        table_name="wallet_position_snapshots",
    )
    op.drop_index(
        "ix_wallet_position_snapshots_wallet_address",
        table_name="wallet_position_snapshots",
    )
    op.drop_table("wallet_position_snapshots")
