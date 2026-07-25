# STATE111 — migration exercise + model/DDL parity harness

Branch: `loop111-migharness/node` (worktree `E:/polymarket-worktrees/loop111-migharness`, base `9d447a3`)

## Problem

`backend/tests/conftest.py` builds every test schema with
`Base.metadata.create_all` against `sqlite+aiosqlite:///:memory:`. **No alembic
migration has ever been executed by the test suite.** Drift between
`app/db/models.py` and the migration DDL was closed by hand twice this week
(revisions 065, 066). Nothing automated would have caught it.

## Charter (delivered)

- `backend/tests/test_migration_exercise.py` (new)
- `backend/tests/migration_parity_baseline.json` (new — recorded pre-existing drift)
- `STATE111.md` (this file)

No migrations added. No dependency added. No deploy script touched.
`PAPER_TRADING_ONLY` untouched.

## Scratch-DB strategy and why

The migrations are **PostgreSQL-only** — `CREATE TYPE ... AS ENUM`,
`ALTER TYPE ... ADD VALUE IF NOT EXISTS`, `postgresql.JSONB` (10x),
`postgresql.UUID` (54x), `postgresql.ENUM` (12x), `server_default=sa.text("now()")`
(37x). SQLite cannot execute them, so there is **no honest portable fallback**;
faking one would mean testing a schema the production DB never sees.

Chosen: **option (a) — env-provided PostgreSQL DSN in
`TEST_MIGRATION_DATABASE_URL`, with a loud skip when absent.**

- No new dependency. `psycopg2-binary>=2.9.10` is already a first-class runtime
  dependency, so the sync driver alembic needs is present today.
- Rejected `testcontainers` / `pytest-postgresql`: neither is in `uv.lock`, and
  adding a Docker-dependent test dependency to every developer's `--extra dev`
  install is a heavier tradeoff than an env-gated skip.

**Safety**: the DSN is used only as an *admin* connection. The harness
`CREATE DATABASE`s a fresh `alphaedge_migtest_<random12>`, migrates only that,
and drops it (terminating stragglers first) in the fixture teardown. The
database named in the DSN is never migrated. Non-local hosts are refused
outright unless `TEST_MIGRATION_ALLOW_REMOTE_SCRATCH=1` is set explicitly, so a
stray production DSN cannot be exercised by accident. Nothing but a sanitized
`host:port/db` (credentials stripped) is ever printed — no secret is logged.

## What the harness does

1. `test_migration_upgrade_downgrade_upgrade` — on the scratch DB:
   `upgrade head` -> `downgrade base` (all 65 revisions, not just -3) ->
   `upgrade head`; then asserts a single alembic head, that `alembic_version`
   matches it, and that application tables exist.
2. `test_model_ddl_parity` — reflects the migrated schema and diffs it against
   `Base.metadata` via `alembic.autogenerate.compare_metadata`
   (`compare_type=True`). Tracked kinds: added/removed table, added/removed
   column, type mismatch, nullability mismatch, unique-constraint mismatch.
   Index-name and `server_default` churn is deliberately excluded as noise.
   Failures print a readable `DRIFT | OBJECT | DETAIL` table.
3. `test_drift_detector_flags_missing_tables_and_columns` — pure-logic
   self-test on synthetic alembic diffs. **Runs everywhere, no DB needed**, so a
   bug in the reporting layer cannot make the parity test silently green.

### Ratchet, and why it is a ratchet

The first real run found **125 genuine drift entries, all pre-existing**:
114 nullability mismatches (revision `001_initial_schema.py` writes e.g.
`sa.Column("cash_balance", sa.Numeric(18, 4), default=0)` — a client-side
default and a *nullable* column — while the model declares `nullable=False`),
10 `JSONB` vs `JSON` type mismatches, and 1 extra unique constraint
(`markets_slug_key`). Fixing those requires new migrations, which is outside
this charter.

Notably: **zero missing/extra tables and zero missing/extra columns** — the
065/066 hand-fixes did close those, which is exactly the class of defect this
harness now guards.

So the parity test is a ratchet: known drift is frozen in
`tests/migration_parity_baseline.json` and the test fails only on drift **not**
in the baseline. Regenerate deliberately with
`UPDATE_MIGRATION_PARITY_BASELINE=1`. Entries that get fixed are reported as
stale (shrink the file) but do not fail the run — the list may shrink, never
silently grow.

Verified adversarially: a temporary test injected a table into `Base.metadata`
and the parity test raised with `loop111_injected` in the drift table
(`1 passed`); the temp file was deleted afterwards.

## Stop condition — commands and results

```
cd backend && uv run --extra dev pytest -q tests/test_migration_exercise.py --basetemp=E:/polymarket-worktrees/loop111-migharness/.pt
```

Canonical form, no DSN in env — the honest skip:

```
ss.                                                                      [100%]
1 passed, 2 skipped in 5.69s

SKIPPED [1] tests\test_migration_exercise.py:187: MIGRATION EXERCISE SKIPPED: no
TEST_MIGRATION_DATABASE_URL set. The alembic migrations are PostgreSQL-only
(CREATE TYPE ... AS ENUM, JSONB, postgresql.UUID), so they cannot run on the
suite's default sqlite+aiosqlite engine. Export a PostgreSQL admin DSN to enable
this harness, e.g.
TEST_MIGRATION_DATABASE_URL=postgresql://<user>:<pw>@localhost:5432/postgres
SKIPPED [1] tests\test_migration_exercise.py:342: (same reason)
```

Same command with a local scratch PostgreSQL reachable — **the exercise
actually running** (DSN supplied via env; value not recorded here):

```
TEST_MIGRATION_DATABASE_URL=<local scratch postgres> \
  uv run --extra dev pytest -q tests/test_migration_exercise.py \
  --basetemp=E:/polymarket-worktrees/loop111-migharness/.pt -s

[loop111] scratch database created: alphaedge_migtest_<random> on localhost:5432/postgres
[loop111] model/DDL parity: 125 total drift entries, 125 baselined, 0 new
3 passed in 20.74s
```

Lint:

```
uv run --extra dev ruff check app tests
All checks passed!
```

Full suite:

```
cd backend && uv run --extra dev pytest -q --basetemp=E:/polymarket-worktrees/loop111-migharness/.pt
2143 passed, 30 skipped in 453.60s (0:07:33)
```

(Two of the 30 skips are this module's DB-gated tests.)

## Auditor notes

- To reproduce the running path you need any local PostgreSQL with CREATEDB
  rights; export `TEST_MIGRATION_DATABASE_URL` pointed at its maintenance DB.
  With no PostgreSQL, the honest skip is the expected result and the full suite
  is still green.
- Do not run `pytest -p no:logging` on the whole suite: `caplog`-using modules
  error out. (Cost one detour here.)
- The baseline is generated on PostgreSQL 17 locally; a materially different
  server version could shift the `JSONB`/`JSON` type rows.

AutoLab: not applicable (no iterative measure — one-shot harness, no metric axis).
