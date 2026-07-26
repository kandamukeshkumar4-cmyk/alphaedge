"""loop114: widen external identifier columns to TEXT

Revision ID: 069_ident_text
Revises: 068_sluglen_text
Create Date: 2026-07-26

Why
---
Prod hit value too long for varchar(128) twice on different tables
(venue_market_matches fixed in 068; wallet_position_snapshots.market_slug
live error breaking whale boot catch-up). This revision sweeps remaining
open-ended identifier columns (market slug, external market id, wallet
address, similar) from String(N<=256) to unbounded TEXT.

Enum-like/status/short-code columns are left alone. venue match/gap slugs
were already TEXT in 068 and are not listed here.

Deploy resilience
-----------------
Mirrors 067/068: one short transaction per table inside an alembic
autocommit_block(), SET LOCAL lock_timeout, retries, information_schema
idempotency, sorted table/column order.

Downgrade: VARCHAR(128) USING left(col, 128).

PAPER_TRADING_ONLY and the order path are untouched.
"""

from __future__ import annotations

import logging
import time
from typing import Iterable, Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.exc import DBAPIError


revision: str = "069_ident_text"
down_revision: Union[str, Sequence[str], None] = "068_sluglen_text"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

LOCK_TIMEOUT = "5s"
STATEMENT_TIMEOUT = "60s"
MAX_ATTEMPTS = 3
RETRY_SLEEP_SECONDS = (1.0, 3.0)

RETRYABLE_SQLSTATES = frozenset({"40P01", "55P03", "57014", "40001"})

# (table, column) — only the slug identifier columns that were VARCHAR(128).
IDENT_COLUMNS: tuple[tuple[str, str], ...] = (
    ('agent_clone_runs', 'market_slug'),
    ('agent_memories', 'market_slug'),
    ('analyst_briefs', 'market_slug'),
    ('analyst_briefs', 'trigger_event_id'),
    ('backtest_runs', 'market_slug'),
    ('brief_claims', 'market_slug'),
    ('external_markets', 'external_id'),
    ('feature_snapshots', 'market_slug'),
    ('heartbeat_decision_logs', 'position_ref'),
    ('market_resolutions', 'slug'),
    ('market_sentiment_snapshots', 'market_slug'),
    ('markets', 'clob_token_id'),
    ('markets', 'external_id'),
    ('markets', 'external_slug'),
    ('markets', 'slug'),
    ('odds_snapshots', 'event_id'),
    ('odds_snapshots', 'market_slug'),
    ('odds_snapshots', 'platform_market_id'),
    ('paper_orders', 'slug'),
    ('prediction_logs', 'market_slug'),
    ('research_sessions', 'market_slug'),
    ('signal_events', 'market_id'),
    ('tracked_wallets', 'wallet_address'),
    ('wallet_position_snapshots', 'market_slug'),
    ('wallet_position_snapshots', 'wallet_address'),
    ('wallet_positions', 'market_id'),
    ('watchlists', 'slug'),
    ('whale_events', 'market_id'),
    ('whale_events', 'market_slug'),
    ('whale_events', 'tx_hash'),
    ('whale_events', 'wallet'),
)


def _columns_by_table() -> list[tuple[str, list[str]]]:
    grouped: dict[str, list[str]] = {}
    for table, column in IDENT_COLUMNS:
        grouped.setdefault(table, []).append(column)
    return [(t, sorted(cols)) for t, cols in sorted(grouped.items())]


def _require_online() -> None:
    if op.get_context().as_sql:  # pragma: no cover - offline mode unused
        raise RuntimeError(
            "069_ident_text cannot run in alembic offline (--sql) mode: it "
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
        logger.warning("069: ROLLBACK after a failed batch did not succeed")


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
                    "069: table %r batch hit SQLSTATE %s on attempt %d/%d "
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
                f"069_ident_text: could not complete the batch for table "
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
                logger.warning("069: table %r not found; skipping batch", table)
                continue
            todo = [col for col in columns if _needs_widen(types.get(col))]
            if not todo:
                logger.info("069: %r ident columns already TEXT; skipped", table)
                continue
            statements = [
                f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE TEXT'
                for col in todo
            ]
            _run_batch(bind, table, statements)
            logger.info("069: %r -> TEXT on %s", table, ", ".join(todo))


def downgrade() -> None:
    _require_online()
    bind = op.get_bind()
    with op.get_context().autocommit_block():
        for table, columns in _columns_by_table():
            types = _column_types(bind, table)
            if not types:
                logger.warning("069: table %r not found; skipping batch", table)
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
            logger.info("069: %r -> VARCHAR(128) on %s", table, ", ".join(todo))
