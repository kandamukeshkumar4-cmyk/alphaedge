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

Deploy resilience (why this file is not just a list of ALTERs)
--------------------------------------------------------------
The first production attempt of this revision died with
``psycopg2.errors.DeadlockDetected`` and was rolled back (production stayed on
066). Cause: a Railway rolling deploy keeps the *old* app instance's ~32 loops
writing to these same tables while a single big migration transaction takes
``ACCESS EXCLUSIVE`` locks across many tables in sequence. Live writers acquire
their locks in a different order, so the two lock chains cross and PostgreSQL
kills one of them. A scratch-database exercise cannot reproduce this: there are
no concurrent writers.

Four changes make the migration survive that environment:

1. **One short transaction per table.** The whole run happens inside an alembic
   ``autocommit_block()``; each table's batch is bracketed by explicit
   ``BEGIN``/``COMMIT``. A deadlock can therefore cost one table's batch, never
   the whole migration, and locks are released between tables instead of being
   held until the end.
2. **Bounded lock waiting.** Every batch sets ``lock_timeout`` and
   ``statement_timeout`` (``SET LOCAL``), so the migration yields to live
   traffic rather than queueing behind it — and ``statement_timeout`` also caps
   the table scan that ``SET NOT NULL`` performs while holding the lock.
3. **Retries.** A batch that fails on a retryable SQLSTATE (deadlock, lock
   timeout, statement timeout, serialization failure) is retried up to
   ``MAX_ATTEMPTS`` times with a short sleep. Exhausting the retries raises with
   a message naming the table.
4. **Idempotency.** Because commits now happen per table, a crashed run must be
   resumable: each batch re-reads ``information_schema.columns`` and only
   touches columns that are still in the wrong state. Re-running ``upgrade``
   after a partial success is a no-op for the tables already done. ``downgrade``
   applies the same guard in reverse.

Tables are processed in sorted order (and columns sorted within a table) so the
lock order is deterministic across upgrade, downgrade and retries.

PAPER_TRADING_ONLY and the RiskService -> OrderIntent -> OrderBookService order
path are untouched: this revision only tightens column nullability.
"""

from __future__ import annotations

import logging
import time
from typing import Iterable, Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.exc import DBAPIError


revision: str = "067_notnull_parity"
down_revision: Union[str, Sequence[str], None] = "066_alpha_validation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

# Deploy-resilience knobs. lock_timeout is deliberately short: if a live writer
# holds the table, we back off and retry rather than block the whole deploy.
LOCK_TIMEOUT = "5s"
STATEMENT_TIMEOUT = "60s"
MAX_ATTEMPTS = 3
RETRY_SLEEP_SECONDS = (1.0, 3.0)  # slept before attempt 2 and attempt 3

# 40P01 deadlock_detected, 55P03 lock_not_available (lock_timeout),
# 57014 query_canceled (statement_timeout), 40001 serialization_failure.
RETRYABLE_SQLSTATES = frozenset({"40P01", "55P03", "57014", "40001"})


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
    ("job_runs", "started_at", "now()"),
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


def _fixes_by_table() -> list[tuple[str, list[tuple[str, str]]]]:
    """``NOT_NULL_FIXES`` regrouped per table, tables and columns sorted.

    Sorting is what makes the lock order deterministic between upgrade,
    downgrade and any retry.
    """
    grouped: dict[str, list[tuple[str, str]]] = {}
    for table, column, fill in NOT_NULL_FIXES:
        grouped.setdefault(table, []).append((column, fill))
    return [(t, sorted(grouped[t])) for t in sorted(grouped)]


def _require_online() -> None:
    if op.get_context().as_sql:  # pragma: no cover - offline mode is unused here
        raise RuntimeError(
            "067_notnull_parity cannot run in alembic offline (--sql) mode: it "
            "reads information_schema to stay idempotent and manages its own "
            "per-table transactions. Run it against a live connection."
        )


def _nullability(bind, table: str) -> dict[str, bool]:
    """``{column: is_nullable}`` for ``table`` in the current schema.

    Empty dict when the table does not exist. This read takes no locks beyond
    a catalog snapshot, so it runs outside the batch transaction.
    """
    rows = bind.execute(
        sa.text(
            "SELECT column_name, is_nullable FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = :t"
        ),
        {"t": table},
    ).fetchall()
    return {r[0]: (r[1] == "YES") for r in rows}


def _rollback_quietly(bind) -> None:
    try:
        bind.exec_driver_sql("ROLLBACK")
    except Exception:  # pragma: no cover - best effort cleanup
        logger.warning("067: ROLLBACK after a failed batch did not succeed")


def _sqlstate(exc: DBAPIError) -> str | None:
    return getattr(exc.orig, "pgcode", None)


def _run_batch(bind, table: str, statements: Iterable[str]) -> None:
    """Run one table's statements in its own short, retried transaction."""
    statements = list(statements)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            bind.exec_driver_sql("BEGIN")
            bind.exec_driver_sql(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'")
            bind.exec_driver_sql(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'")
            for stmt in statements:
                bind.exec_driver_sql(stmt)
            bind.exec_driver_sql("COMMIT")
            return
        except DBAPIError as exc:
            _rollback_quietly(bind)
            state = _sqlstate(exc)
            retryable = state in RETRYABLE_SQLSTATES
            if retryable and attempt < MAX_ATTEMPTS:
                pause = RETRY_SLEEP_SECONDS[attempt - 1]
                logger.warning(
                    "067: table %r batch hit SQLSTATE %s on attempt %d/%d "
                    "(live writers hold the lock); retrying in %.1fs",
                    table,
                    state,
                    attempt,
                    MAX_ATTEMPTS,
                    pause,
                )
                time.sleep(pause)
                continue
            raise RuntimeError(
                f"067_notnull_parity: could not complete the batch for table "
                f"{table!r} (SQLSTATE {state}, attempt {attempt}/{MAX_ATTEMPTS}"
                f"{', retryable' if retryable else ', not retryable'}). Earlier "
                "tables are already committed, so re-running `alembic upgrade "
                "head` resumes from here — each batch skips columns that are "
                "already in the target state. If this keeps happening, quiesce "
                "the writers on this table (scale the old instance to 0) and "
                "re-run."
            ) from exc


def upgrade() -> None:
    _require_online()
    bind = op.get_bind()
    with op.get_context().autocommit_block():
        for table, columns in _fixes_by_table():
            nullability = _nullability(bind, table)
            if not nullability:
                logger.warning("067: table %r not found; skipping batch", table)
                continue
            todo = [
                (col, fill)
                for col, fill in columns
                if nullability.get(col, False)  # still nullable -> work to do
            ]
            if not todo:
                logger.info("067: %r already NOT NULL for all targets; skipped", table)
                continue
            statements = [
                # Backfill first: assignment context types the literal for
                # enum/json/numeric/boolean columns alike, so no cast is needed.
                f'UPDATE "{table}" SET "{col}" = {fill} WHERE "{col}" IS NULL'
                for col, fill in todo
            ] + [
                f'ALTER TABLE "{table}" ALTER COLUMN "{col}" SET NOT NULL'
                for col, _fill in todo
            ]
            _run_batch(bind, table, statements)
            logger.info(
                "067: %r -> NOT NULL on %s", table, ", ".join(c for c, _ in todo)
            )


def downgrade() -> None:
    _require_online()
    bind = op.get_bind()
    with op.get_context().autocommit_block():
        for table, columns in _fixes_by_table():
            nullability = _nullability(bind, table)
            if not nullability:
                logger.warning("067: table %r not found; skipping batch", table)
                continue
            todo = [
                col
                for col, _fill in columns
                if nullability.get(col) is False  # currently NOT NULL -> revert
            ]
            if not todo:
                continue
            _run_batch(
                bind,
                table,
                [
                    f'ALTER TABLE "{table}" ALTER COLUMN "{col}" DROP NOT NULL'
                    for col in todo
                ],
            )
