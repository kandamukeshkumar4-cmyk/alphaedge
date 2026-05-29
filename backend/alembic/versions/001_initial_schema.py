"""Initial schema — Week 1 core + Week 2-4 tables

Revision ID: 001
Revises:
Create Date: 2025-01-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE market_status AS ENUM ('open', 'locked', 'resolved')")
    op.execute("CREATE TYPE order_side AS ENUM ('buy', 'sell')")
    op.execute("CREATE TYPE order_outcome AS ENUM ('yes', 'no')")
    op.execute("CREATE TYPE order_type AS ENUM ('limit', 'market')")
    op.execute("CREATE TYPE order_status AS ENUM ('open', 'partial', 'filled', 'cancelled')")
    op.execute(
        "CREATE TYPE ledger_entry_type AS ENUM ('deposit', 'withdraw', 'trade', 'settlement')"
    )

    market_status = postgresql.ENUM("open", "locked", "resolved", name="market_status", create_type=False)
    order_side = postgresql.ENUM("buy", "sell", name="order_side", create_type=False)
    order_outcome = postgresql.ENUM("yes", "no", name="order_outcome", create_type=False)
    order_type = postgresql.ENUM("limit", "market", name="order_type", create_type=False)
    order_status = postgresql.ENUM(
        "open", "partial", "filled", "cancelled", name="order_status", create_type=False
    )
    ledger_entry_type = postgresql.ENUM(
        "deposit", "withdraw", "trade", "settlement", name="ledger_entry_type", create_type=False
    )

    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("is_system", sa.Boolean(), default=False),
        sa.Column("cash_balance", sa.Numeric(18, 4), default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "markets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(128), unique=True, nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", market_status, server_default="open"),
        sa.Column("lock_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("winning_outcome", order_outcome, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_markets_slug", "markets", ["slug"])

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id")),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id")),
        sa.Column("side", order_side),
        sa.Column("outcome", order_outcome),
        sa.Column("order_type", order_type),
        sa.Column("price", sa.Numeric(6, 4), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4)),
        sa.Column("filled_quantity", sa.Numeric(18, 4), server_default="0"),
        sa.Column("status", order_status, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "fills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id")),
        sa.Column("buy_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id")),
        sa.Column("sell_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id")),
        sa.Column("outcome", order_outcome),
        sa.Column("price", sa.Numeric(6, 4)),
        sa.Column("quantity", sa.Numeric(18, 4)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id")),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id")),
        sa.Column("yes_shares", sa.Numeric(18, 4), server_default="0"),
        sa.Column("no_shares", sa.Numeric(18, 4), server_default="0"),
        sa.Column("avg_yes_cost", sa.Numeric(6, 4), server_default="0"),
        sa.Column("avg_no_cost", sa.Numeric(6, 4), server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id")),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id"), nullable=True),
        sa.Column("entry_type", ledger_entry_type),
        sa.Column("amount", sa.Numeric(18, 4)),
        sa.Column("balance_after", sa.Numeric(18, 4)),
        sa.Column("description", sa.Text(), default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "domain_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(64)),
        sa.Column("payload", postgresql.JSONB(), server_default="{}"),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Week 2+
    op.create_table(
        "odds_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("market_slug", sa.String(128)),
        sa.Column("implied_yes", sa.Numeric(6, 4)),
        sa.Column("source", sa.String(64)),
        sa.Column("captured_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "feature_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("market_slug", sa.String(128)),
        sa.Column("features", postgresql.JSONB()),
        sa.Column("feature_hash", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "model_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128)),
        sa.Column("version", sa.String(32)),
        sa.Column("artifact_path", sa.String(512)),
        sa.Column("metrics", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "feature_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128)),
        sa.Column("version", sa.String(32)),
        sa.Column("schema_hash", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "dataset_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128)),
        sa.Column("row_count", sa.Integer()),
        sa.Column("checksum", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "training_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("model_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("model_versions.id")),
        sa.Column(
            "dataset_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dataset_snapshots.id"),
            nullable=True,
        ),
        sa.Column("status", sa.String(32)),
        sa.Column("metrics", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "prediction_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id"), nullable=True),
        sa.Column("market_slug", sa.String(128)),
        sa.Column("model_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("model_versions.id"), nullable=True),
        sa.Column("feature_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("feature_versions.id"), nullable=True),
        sa.Column("input_feature_hash", sa.String(64), nullable=True),
        sa.Column("odds_snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("odds_snapshots.id"), nullable=True),
        sa.Column("predicted_prob", sa.Numeric(6, 4)),
        sa.Column("confidence", sa.Numeric(6, 4)),
        sa.Column("predicted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("lock_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Week 3
    op.create_table(
        "evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id")),
        sa.Column("brier_score", sa.Numeric(8, 6)),
        sa.Column("predicted_prob", sa.Numeric(6, 4), nullable=True),
        sa.Column("actual_outcome", sa.Integer()),
        sa.Column("closing_implied", sa.Numeric(6, 4), nullable=True),
        sa.Column("pnl", sa.Numeric(18, 4)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "eval_aggregates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("window_days", sa.Integer()),
        sa.Column("mean_brier", sa.Numeric(8, 6)),
        sa.Column("calibration_error", sa.Numeric(8, 6)),
        sa.Column("market_count", sa.Integer()),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("alert_type", sa.String(64)),
        sa.Column("message", sa.Text()),
        sa.Column("payload", postgresql.JSONB()),
        sa.Column("acknowledged", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Week 4
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id")),
        sa.Column("status", sa.String(32)),
        sa.Column("graph_version", sa.String(32)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "agent_run_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id")),
        sa.Column("step_name", sa.String(64)),
        sa.Column("input_data", postgresql.JSONB()),
        sa.Column("output_data", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "prompt_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128)),
        sa.Column("version", sa.String(32)),
        sa.Column("content", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "failed_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_name", sa.String(128)),
        sa.Column("payload", postgresql.JSONB()),
        sa.Column("error", sa.Text()),
        sa.Column("attempts", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "job_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_name", sa.String(128)),
        sa.Column("status", sa.String(32)),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    for t in [
        "job_runs",
        "failed_jobs",
        "prompt_versions",
        "agent_run_steps",
        "agent_runs",
        "alerts",
        "eval_aggregates",
        "evaluations",
        "prediction_logs",
        "training_runs",
        "dataset_snapshots",
        "feature_versions",
        "model_versions",
        "feature_snapshots",
        "odds_snapshots",
        "domain_events",
        "ledger",
        "positions",
        "fills",
        "orders",
        "markets",
        "accounts",
    ]:
        op.drop_table(t)
    for e in [
        "ledger_entry_type",
        "order_status",
        "order_type",
        "order_outcome",
        "order_side",
        "market_status",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {e}")
