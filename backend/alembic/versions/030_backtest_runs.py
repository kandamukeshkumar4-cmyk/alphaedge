"""U10 backtest_runs table — stores replay results for nightly track-record publishing.

Revision ID: 030_backtest_runs
Revises: 029_agent_clones
Create Date: 2026-07-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "030_backtest_runs"
down_revision: Union[str, Sequence[str], None] = "029_agent_clones"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("market_slug", sa.String(128), nullable=False),
        sa.Column("clone_id", sa.String(128), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("initial_equity", sa.Numeric(18, 4), nullable=False, server_default="10000"),
        sa.Column("final_equity", sa.Numeric(18, 4), nullable=True),
        sa.Column("spread", sa.Numeric(8, 6), nullable=False, server_default="0.02"),
        sa.Column(
            "slippage_per_unit", sa.Numeric(10, 8), nullable=False, server_default="0.001"
        ),
        sa.Column("edge_threshold", sa.Numeric(6, 4), nullable=False, server_default="0.05"),
        sa.Column("snapshot_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trade_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("brier_final", sa.Numeric(8, 6), nullable=True),
        sa.Column("no_lookahead_verified", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("insufficient_data", sa.Boolean(), nullable=False, server_default="false"),
        # JSON columns for equity curve, fill stats, Brier series.
        sa.Column("equity_curve", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("fill_quality", sa.JSON(), nullable=True),
        sa.Column("brier_over_time", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(32), nullable=False, server_default="completed"),
        sa.Column("paper_trading_only", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_backtest_runs_market_slug", "backtest_runs", ["market_slug"])
    op.create_index("ix_backtest_runs_created_at", "backtest_runs", ["created_at"])


def downgrade() -> None:
    op.drop_table("backtest_runs")
