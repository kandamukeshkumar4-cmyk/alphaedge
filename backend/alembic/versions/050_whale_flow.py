"""whale flow events table (Loop V58 D1)

Revision ID: 050_whale_flow
Revises: 047_social
Create Date: 2026-07-17

V57 coordinates on 049; V58 starts at 050.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "050_whale_flow"
down_revision: Union[str, Sequence[str], None] = "047_social"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "whale_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("wallet", sa.String(length=64), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("outcome", sa.String(length=8), nullable=False, server_default="YES"),
        sa.Column("size", sa.Numeric(18, 4), nullable=False),
        sa.Column("price", sa.Numeric(10, 4), nullable=False),
        sa.Column("notional", sa.Numeric(18, 4), nullable=False),
        sa.Column("market_slug", sa.String(length=128), nullable=False),
        sa.Column("market_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("tx_hash", sa.String(length=128), nullable=True),
        sa.Column(
            "trade_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="polymarket.data-api"),
    )
    op.create_index(
        "ix_whale_events_market_captured",
        "whale_events",
        ["market_slug", "captured_at"],
    )
    op.create_index("ix_whale_events_wallet", "whale_events", ["wallet"])
    op.create_index(
        "ix_whale_events_tx_hash",
        "whale_events",
        ["tx_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_whale_events_tx_hash", table_name="whale_events")
    op.drop_index("ix_whale_events_wallet", table_name="whale_events")
    op.drop_index("ix_whale_events_market_captured", table_name="whale_events")
    op.drop_table("whale_events")
