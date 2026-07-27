"""loop116: store the rendered dashboard artifact on each scanner run

Revision ID: 070_scanner_run_artifact
Revises: 069_ident_text
Create Date: 2026-07-27

Why
---
A finished scanner run persists ``scanner_runs.result`` (raw candidates +
counts). The user-facing payoff is a rendered document — headline, fired pill,
KPI tiles, per-step counters, matched-markets table, chart series and two short
narrative sections. That document is assembled once at run completion (its
narrative may involve one LLM call) so reads never re-pay for it, which means it
needs its own column. ``checkpoint`` holds resume state and ``result`` is an
already-consumed API contract, so neither is reusable.

Additive and nullable: existing rows keep NULL and the artifact endpoint
assembles deterministically on read for them.

Deploy resilience
-----------------
Mirrors 067/068/069: the DDL runs in its own short transaction inside an
alembic ``autocommit_block()`` with ``SET LOCAL lock_timeout``, bounded retries
on the usual transient SQLSTATEs, and an ``information_schema`` idempotency
check so a partial or replayed deploy is a no-op. ``ADD COLUMN ... NULL`` takes
only a brief ACCESS EXCLUSIVE lock and never rewrites the table.

Downgrade: DROP COLUMN (the artifact is derived data — nothing is lost that the
service cannot rebuild from ``result``).

PAPER_TRADING_ONLY and the order path are untouched.
"""

from __future__ import annotations

import logging
import time
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.exc import DBAPIError

revision: str = "070_scanner_run_artifact"
down_revision: Union[str, Sequence[str], None] = "069_ident_text"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

TABLE = "scanner_runs"
COLUMN = "artifact"

LOCK_TIMEOUT = "5s"
STATEMENT_TIMEOUT = "60s"
MAX_ATTEMPTS = 3
RETRY_SLEEP_SECONDS = (1.0, 3.0)

RETRYABLE_SQLSTATES = frozenset({"40P01", "55P03", "57014", "40001"})


def _require_online() -> None:
    if op.get_context().as_sql:
        raise RuntimeError(
            "070_scanner_run_artifact cannot run in alembic offline (--sql) "
            "mode: it reads information_schema to stay idempotent and manages "
            "its own transaction. Run it against a live connection."
        )


def _column_exists(bind) -> bool:
    row = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = :t AND column_name = :c"
        ),
        {"t": TABLE, "c": COLUMN},
    ).first()
    return row is not None


def _rollback_quietly(bind) -> None:
    try:
        bind.exec_driver_sql("ROLLBACK")
    except Exception:  # pragma: no cover - best effort cleanup
        logger.warning("070: ROLLBACK after a failed statement did not succeed")


def _sqlstate(exc: DBAPIError) -> str | None:
    return getattr(exc.orig, "pgcode", None)


def _run(bind, statement: str) -> None:
    """Run one DDL statement in its own short, retried transaction."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            bind.exec_driver_sql("BEGIN")
            bind.exec_driver_sql(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'")
            bind.exec_driver_sql(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'")
            bind.exec_driver_sql(statement)
            bind.exec_driver_sql("COMMIT")
            return
        except DBAPIError as exc:
            _rollback_quietly(bind)
            state = _sqlstate(exc)
            if state in RETRYABLE_SQLSTATES and attempt < MAX_ATTEMPTS:
                pause = RETRY_SLEEP_SECONDS[attempt - 1]
                logger.warning(
                    "070: %s hit SQLSTATE %s on attempt %d/%d (live writers hold "
                    "the lock); retrying in %.1fs",
                    TABLE,
                    state,
                    attempt,
                    MAX_ATTEMPTS,
                    pause,
                )
                time.sleep(pause)
                continue
            raise RuntimeError(
                f"070_scanner_run_artifact: could not alter {TABLE!r} "
                f"(SQLSTATE {state}, attempt {attempt}/{MAX_ATTEMPTS}). The "
                "revision is idempotent, so re-running `alembic upgrade head` "
                "is safe. If it keeps failing, quiesce writers on scanner_runs "
                "and re-run."
            ) from exc


def upgrade() -> None:
    _require_online()
    bind = op.get_bind()
    with op.get_context().autocommit_block():
        if _column_exists(bind):
            logger.info("070: %s.%s already present; skipped", TABLE, COLUMN)
            return
        _run(bind, f'ALTER TABLE "{TABLE}" ADD COLUMN IF NOT EXISTS "{COLUMN}" JSON')


def downgrade() -> None:
    _require_online()
    bind = op.get_bind()
    with op.get_context().autocommit_block():
        if not _column_exists(bind):
            logger.info("070: %s.%s already absent; skipped", TABLE, COLUMN)
            return
        _run(bind, f'ALTER TABLE "{TABLE}" DROP COLUMN IF EXISTS "{COLUMN}"')
