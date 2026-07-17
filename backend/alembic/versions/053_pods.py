"""pod strategy tables (Loop V57 P1).

This checkout intentionally has 048 as its local Alembic head. The integration
orchestrator re-chains this migration above 052 when the concurrent migration
waves merge; do not change this temporary local parent here.

Revision ID: 053_pods
Revises: 048_lock_provenance
Create Date: 2026-07-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "053_pods"
down_revision: Union[str, Sequence[str], None] = "048_lock_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pods",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_pods_enabled", "pods", ["enabled"], unique=False)
    op.create_table(
        "pod_trades",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pod_id", sa.Uuid(), nullable=False),
        sa.Column("market_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("outcome", sa.String(length=3), nullable=True),
        sa.Column("price", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("fee", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("slippage", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("score_components", sa.JSON(), nullable=False),
        sa.Column("decision", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["pod_id"], ["pods.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pod_trades_pod_created", "pod_trades", ["pod_id", "created_at"], unique=False)
    op.create_index("ix_pod_trades_market", "pod_trades", ["market_id"], unique=False)
    op.create_table(
        "pod_equity_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pod_id", sa.Uuid(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("cash_balance", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("positions_mtm", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("equity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.ForeignKeyConstraint(["pod_id"], ["pods.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pod_id", "captured_at", name="uq_pod_equity_snapshot"),
    )
    op.create_index("ix_pod_equity_pod_captured", "pod_equity_snapshots", ["pod_id", "captured_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pod_equity_pod_captured", table_name="pod_equity_snapshots")
    op.drop_table("pod_equity_snapshots")
    op.drop_index("ix_pod_trades_market", table_name="pod_trades")
    op.drop_index("ix_pod_trades_pod_created", table_name="pod_trades")
    op.drop_table("pod_trades")
    op.drop_index("ix_pods_enabled", table_name="pods")
    op.drop_table("pods")
