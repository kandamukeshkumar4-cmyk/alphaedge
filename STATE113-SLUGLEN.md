# STATE113-SLUGLEN — venue slug VARCHAR(128) → TEXT

**Role:** Backend engineer (Cursor Grok 4.5 High), worktree `loop113-sluglen`
**Branch:** `loop113-sluglen/node`
**Commit:** `056e817` — `fix(loop113): widen venue match/gap slugs to Text`

## Bug

Venue matcher catalog_limit=500 finds real cross-venue pairs, but persisting
them crashed with asyncpg `StringDataRightTruncationError` (value too long for
`character varying(128)`). The venue_gap loop died pre-heartbeat (status
`never` in `/api/v1/system/loops`). Markets beyond rank ~200 have slugs longer
than the 128-char columns.

## Fix

1. **Models** (`backend/app/db/models.py`): `VenueMarketMatch.pm_slug` /
   `ks_slug` and `VenueGap.pm_slug` / `ks_slug` — `String(128)` → `Text`.
   Titles stay `String(512)`. No other schema changes.
2. **Migration 068** (`backend/alembic/versions/068_sluglen_text.py`): chains
   on `067_notnull_parity`; ALTER those four columns to TEXT. Downgrade:
   `VARCHAR(128) USING left(col, 128)`. Deploy-resilience mirrored from 067
   (per-table txn, `SET LOCAL lock_timeout='5s'`, retries, information_schema
   idempotency).
3. **Upsert comment** (`venue_match_service.upsert_matches`): notes 068 /
   do-not-re-tighten. No defensive truncate — Text is enough.
4. **Tests** (`backend/tests/test_loop113_sluglen.py`):
   - `test_long_slugs_persist_in_match_upsert` (200-char pair roundtrip)
   - `test_migration_068_single_head`

## Guardrails

PAPER_TRADING_ONLY untouched. No order-path / LLM changes. No secrets printed.
No push/deploy. Explicit `git add` of charter files only (no `git add -A`).

## MODEL/DDL PARITY

`tests/test_migration_exercise.py` not run: no `TEST_MIGRATION_DATABASE_URL`
scratch DSN in this environment. Model + migration agree on TEXT for the four
slug columns; harness must be re-run where a scratch Postgres exists.

## AutoLab

AutoLab: not applicable (no iterative measure) — one-shot schema widen.

## STOP proof (verbatim)

### targeted pytest (new file + tests/test_loop112_matcher.py)

```text
.........................                                                [100%]
25 passed in 6.85s
```

### ruff

```text
All checks passed!
```

### alembic heads (single 068)

```text
068_sluglen_text (head)
```

### full suite summary line

```text
2198 passed, 30 skipped in 416.75s (0:06:56)
```

### orchestration/gate.py

```text
=== GATE VERDICT ===
PASS: all checks green
```

