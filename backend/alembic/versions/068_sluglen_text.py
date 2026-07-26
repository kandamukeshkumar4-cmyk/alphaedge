"""loop113: widen venue match/gap slug columns to TEXT

Revision ID: 068_sluglen_text
Revises: 067_notnull_parity
Create Date: 2026-07-26

Why
---
The venue matcher's widened scan window (catalog_limit=500) finds real
cross-venue pairs beyond rank ~200, but persisting them crashed with
asyncpg StringDataRightTruncationError: value too long for character
varying(128). Market slugs are identifiers, not fixed-width data — the
VARCHAR(128) columns on venue_market_matches / venue_gaps were the wrong
type.

This revision ALTERs exactly those four columns (pm_slug, ks_slug on each
table) to unbounded TEXT. Titles stay String(512); no other schema changes.

Deploy resilience
-----------------
Mirrors 067_notnull_parity: one short transaction per table inside an
alembic autocommit_block(), SET LOCAL lock_timeout='5s' + statement_timeout,
retries on deadlock/lock/statement timeout, and information_schema idempotency
so a partial run can resume.

Downgrade uses ``USING left(col, 128)`` so values longer than 128 cannot
themselves fail the reverse ALTER.

PAPER_TRADING_ONLY and the RiskService -> OrderIntent -> OrderBookService
order path are untouched.
"""

from __future__ import annotations

import logging
import time
from typing import Iterable, Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.exc import DBAPIError


revision: str = "068_sluglen_text"
down_revision: Union[str, Sequence[str], None] = "067_notnull_parity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

LOCK_TIMEOUT = "5s"
STATEMENT_TIMEOUT = "60s"
MAX_ATTEMPTS = 3
RETRY_SLEEP_SECONDS = (1.0, 3.0)

RETRYABLE_SQLSTATES = frozenset({"40P01", "55P03", "57014", "40001"})

# (table, column) — only the slug identifier columns that were VARCHAR(128).
SLUG_COLUMNS: tuple[tuple[str, str], ...] = (
    ("venue_gaps", "ks_slug"),
    ("venue_gaps", "pm_slug"),
    ("venue_market_matches", "ks_slug"),
    ("venue_market_matches", "pm_slug"),
)


def _columns_by_table() -> list[tuple[str, list[str]]]:
    grouped: dict[str, list[str]] = {}
    for table, column in SLUG_COLUMNS:
        grouped.setdefault(table, []).append(column)
    return [(t, sorted(cols)) for t, cols in sorted(grouped.items())]


def _require_online() -> None:
    if op.get_context().as_sql:  # pragma: no cover - offline mode unused
        raise RuntimeError(
            "068_sluglen_text cannot run in alembic offline (--sql) mode: it "
            "reads information_schema to stay idempotent and manages its own "
            "per-table transactions. Run it against a live connection."
        )


def _column_types(bind, table: str) -> dict[str, tuple[str, int | None]]:
    """``{column: (data_type, character_maximum_length)}`` for ``table``.

    Empty dict when the table does not exist.
    """
    rows = bind.execute(
        sa.text(
            "SELECT column_name, data_type, character_maximum_length "
            "FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = :t"
        ),
        {"t": table},
    ).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def _needs_widen(meta: tuple[str, int | None] | None) -> bool:
    if meta is None:
        return False
    data_type, _max_len = meta
    return data_type != "text"


def _needs_narrow(meta: tuple[str, int | None] | None) -> bool:
    """True when the column is not already VARCHAR(128)."""
    if meta is None:
        return False
    data_type, max_len = meta
    return not (data_type == "character varying" and max_len == 128)


def _rollback_quietly(bind) -> None:
    try:
        bind.exec_driver_sql("ROLLBACK")
    except Exception:  # pragma: no cover - best effort cleanup
        logger.warning("068: ROLLBACK after a failed batch did not succeed")


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
                    "068: table %r batch hit SQLSTATE %s on attempt %d/%d "
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
                f"068_sluglen_text: could not complete the batch for table "
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
        for table, columns in _columns_by_table():
            types = _column_types(bind, table)
            if not types:
                logger.warning("068: table %r not found; skipping batch", table)
                continue
            todo = [col for col in columns if _needs_widen(types.get(col))]
            if not todo:
                logger.info("068: %r slug columns already TEXT; skipped", table)
                continue
            statements = [
                f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE TEXT'
                for col in todo
            ]
            _run_batch(bind, table, statements)
            logger.info("068: %r -> TEXT on %s", table, ", ".join(todo))


def downgrade() -> None:
    _require_online()
    bind = op.get_bind()
    with op.get_context().autocommit_block():
        for table, columns in _columns_by_table():
            types = _column_types(bind, table)
            if not types:
                logger.warning("068: table %r not found; skipping batch", table)
                continue
            todo = [col for col in columns if _needs_narrow(types.get(col))]
            if not todo:
                continue
            # left(..., 128) so values longer than 128 cannot fail the reverse.
            statements = [
                (
                    f'ALTER TABLE "{table}" ALTER COLUMN "{col}" '
                    f"TYPE VARCHAR(128) USING left(\"{col}\", 128)"
                )
                for col in todo
            ]
            _run_batch(bind, table, statements)
            logger.info("068: %r -> VARCHAR(128) on %s", table, ", ".join(todo))
