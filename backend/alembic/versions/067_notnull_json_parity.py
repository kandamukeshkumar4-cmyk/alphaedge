"""loop112: close model/DDL nullability drift left by revision 001

Revision ID: 067_notnull_parity
Revises: 066_alpha_validation
Create Date: 2026-07-25

Why
---
``tests/test_migration_exercise.py`` froze 125 known model-vs-migration drifts
in ``tests/migration_parity_baseline.json``. 114 of them are the same bug:
revision 001 (and a few successors) created columns *without* ``NOT NULL``
while ``app/db/models.py`` declares ``nullable=False``. The models are the
intended contract; the DDL never enforced it.

This revision enforces it for the subset that can be made NOT NULL **safely**.

Safety rule (deliberately conservative)
---------------------------------------
A column is only altered when the model carries a default that tells us what a
legacy NULL *should* have been:

* a Python-side ``default=`` scalar (``0``, ``False``, ``Decimal("0")``, an
  enum member, a literal string, ``dict``/``list``), or
* a ``server_default=now()`` timestamp (rows written through the DDL default
  can never be NULL in the first place; the backfill is belt-and-braces).

Every such column is backfilled first (``UPDATE ... WHERE col IS NULL``) and
only then gets ``SET NOT NULL``, so the migration cannot fail on existing rows.

Columns with **no** default are deliberately skipped even though the models
declare them ``nullable=False`` — foreign keys (``fills.market_id``,
``ledger.account_id``, ...), measurements (``orders.quantity``,
``prediction_logs.predicted_prob``, ...) and free-text/identity fields
(``alerts.message``, ``feature_versions.name``, ...). There is no value we
could invent for a legacy NULL there, and a failed production migration is
worse than a smaller ratchet shrink. They stay in the parity baseline.

PAPER_TRADING_ONLY and the RiskService -> OrderIntent -> OrderBookService order
path are untouched: this revision only tightens column nullability.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "067_notnull_parity"
down_revision: Union[str, Sequence[str], None] = "066_alpha_validation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column, backfill literal/expression used for legacy NULL rows)
# Grouped per table; the expression mirrors the model's own default.
NOT_NULL_FIXES: tuple[tuple[str, str, str], ...] = (
    ("accounts", "cash_balance", "0"),
    ("accounts", "created_at", "now()"),
    ("accounts", "is_system", "false"),
    ("agent_run_steps", "created_at", "now()"),
    ("agent_run_steps", "input_data", "'{}'"),
    ("agent_run_steps", "output_data", "'{}'"),
    ("agent_runs", "created_at", "now()"),
    ("agent_runs", "graph_version", "'v1'"),
    ("agent_runs", "status", "'pending'"),
    ("alerts", "acknowledged", "false"),
    ("alerts", "created_at", "now()"),
    ("alerts", "payload", "'{}'"),
    ("dataset_snapshots", "created_at", "now()"),
    ("dataset_snapshots", "row_count", "0"),
    ("domain_events", "occurred_at", "now()"),
    ("domain_events", "payload", "'{}'"),
    ("eval_aggregates", "computed_at", "now()"),
    ("eval_aggregates", "market_count", "0"),
    ("eval_aggregates", "window_days", "7"),
    ("evaluations", "actual_outcome", "0"),
    ("evaluations", "created_at", "now()"),
    ("evaluations", "pnl", "0"),
    ("external_markets", "created_at", "now()"),
    ("failed_jobs", "attempts", "0"),
    ("failed_jobs", "created_at", "now()"),
    ("failed_jobs", "payload", "'{}'"),
    ("feature_snapshots", "created_at", "now()"),
    ("feature_snapshots", "features", "'{}'"),
    ("feature_versions", "created_at", "now()"),
    ("fills", "created_at", "now()"),
    ("forecast_logs", "locked_at", "now()"),
    ("forecast_scores", "scored_at", "now()"),
    ("forecasters", "created_at", "now()"),
    ("ledger", "created_at", "now()"),
    ("ledger", "description", "''"),
    ("market_snapshots", "captured_at", "now()"),
    ("markets", "created_at", "now()"),
    ("markets", "status", "'open'"),
    ("model_versions", "created_at", "now()"),
    ("model_versions", "metrics", "'{}'"),
    ("odds_snapshots", "source", "'fixture'"),
    ("orders", "created_at", "now()"),
    ("orders", "filled_quantity", "0"),
    ("orders", "status", "'open'"),
    ("paper_signals", "created_at", "now()"),
    ("paper_signals", "updated_at", "now()"),
    ("positions", "avg_no_cost", "0"),
    ("positions", "avg_yes_cost", "0"),
    ("positions", "no_shares", "0"),
    ("positions", "updated_at", "now()"),
    ("positions", "yes_shares", "0"),
    ("prediction_logs", "confidence", "0.5"),
    ("prediction_logs", "predicted_at", "now()"),
    ("prompt_versions", "created_at", "now()"),
    ("signal_events", "created_at", "now()"),
    ("tracked_wallets", "created_at", "now()"),
    ("tracked_wallets", "updated_at", "now()"),
    ("training_runs", "created_at", "now()"),
    ("training_runs", "metrics", "'{}'"),
    ("training_runs", "status", "'completed'"),
    ("venue_market_matches", "reasons", "'[]'"),
    ("wallet_positions", "captured_at", "now()"),
)


def upgrade() -> None:
    for table, column, fill in NOT_NULL_FIXES:
        # Backfill first: assignment context types the literal for enum/json/
        # numeric/boolean columns alike, so no explicit cast is needed.
        op.execute(
            f'UPDATE "{table}" SET "{column}" = {fill} WHERE "{column}" IS NULL'
        )
        op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" SET NOT NULL')


def downgrade() -> None:
    for table, column, _fill in reversed(NOT_NULL_FIXES):
        op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" DROP NOT NULL')
