# STATE112-DRIFT — migration-parity ratchet shrink (loop112)

Branch `loop112-driftfix/node`, based on integration tip `c907973`.

## Result

| | before | after |
|---|---|---|
| baseline entries (`backend/tests/migration_parity_baseline.json`) | 125 | **61** |
| NULLABILITY MISMATCH | 114 | 51 |
| TYPE MISMATCH (db=JSONB models=JSON) | 10 | 10 |
| EXTRA UNIQUE CONSTRAINT `markets_slug_key` | 1 | 0 |

64 drift entries closed (63 in the first pass + 1 from audit finding F1). New revision: `backend/alembic/versions/067_notnull_json_parity.py`
(revision id `067_notnull_parity`, 18 chars, `down_revision = "066_alpha_validation"`).

## 1. Nullability — 63 fixed, 51 deliberately skipped

Safety rule applied (conservative by design): a column is altered **only** when the
model itself tells us what a legacy NULL should have been —

* a Python-side `default=` scalar (`0`, `False`, `Decimal("0")`, an enum member,
  a literal string, `dict`/`list`), or
* `server_default=now()` (rows written through the DDL default cannot be NULL;
  the backfill is belt-and-braces).

Every such column is backfilled first
(`UPDATE "t" SET "c" = <literal> WHERE "c" IS NULL`) and only then gets
`ALTER TABLE ... SET NOT NULL`, so the migration cannot fail on existing prod
rows. ALTERs are grouped per table in `NOT_NULL_FIXES`.

Fixed (63, by table): accounts(cash_balance, created_at, is_system) ·
agent_run_steps(created_at, input_data, output_data) ·
agent_runs(created_at, graph_version, status) · alerts(acknowledged, created_at,
payload) · dataset_snapshots(created_at, row_count) · domain_events(occurred_at,
payload) · eval_aggregates(computed_at, market_count, window_days) ·
evaluations(actual_outcome, created_at, pnl) · external_markets(created_at) ·
failed_jobs(attempts, created_at, payload) · feature_snapshots(created_at,
features) · feature_versions(created_at) · fills(created_at) ·
forecast_logs(locked_at) · forecast_scores(scored_at) · forecasters(created_at) · job_runs(started_at) ·
ledger(created_at, description) · market_snapshots(captured_at) ·
markets(created_at, status) · model_versions(created_at, metrics) ·
odds_snapshots(source) · orders(created_at, filled_quantity, status) ·
paper_signals(created_at, updated_at) · positions(avg_no_cost, avg_yes_cost,
no_shares, updated_at, yes_shares) · prediction_logs(confidence, predicted_at) ·
prompt_versions(created_at) · signal_events(created_at) ·
tracked_wallets(created_at, updated_at) · training_runs(created_at, metrics,
status) · venue_market_matches(reasons) · wallet_positions(captured_at).

**Skipped (51) — no safe default exists.** These stay in the baseline. They are
foreign keys, measurements and identity/free-text fields; there is no value we
could invent for a legacy NULL, and a failed production migration is worse than
a smaller shrink. Closing them needs a prod data audit (`SELECT count(*) ...
WHERE col IS NULL`) per column first:

agent_run_steps.agent_run_id, agent_run_steps.step_name, agent_runs.market_id,
alerts.alert_type, alerts.message, dataset_snapshots.checksum,
dataset_snapshots.name, domain_events.event_type,
eval_aggregates.calibration_error, eval_aggregates.mean_brier,
evaluations.brier_score, evaluations.market_id, failed_jobs.error,
failed_jobs.job_name, feature_snapshots.feature_hash,
feature_snapshots.market_slug, feature_versions.name,
feature_versions.schema_hash, feature_versions.version, fills.buy_order_id,
fills.market_id, fills.outcome, fills.price, fills.quantity,
fills.sell_order_id, job_runs.job_name, job_runs.status,
ledger.account_id, ledger.amount, ledger.balance_after, ledger.entry_type,
model_versions.artifact_path, model_versions.name, model_versions.version,
odds_snapshots.captured_at, odds_snapshots.implied_yes,
odds_snapshots.market_slug, orders.account_id, orders.market_id,
orders.order_type, orders.outcome, orders.quantity, orders.side,
positions.account_id, positions.market_id, prediction_logs.market_slug,
prediction_logs.predicted_prob, prompt_versions.content, prompt_versions.name,
prompt_versions.version, training_runs.model_version_id.

## 2. JSONB-vs-JSON (10) — NOT changed; the brief's direction was inverted

The work order asked for `ALTER TYPE ... TO JSONB`. **That would be a no-op.**
The harness compares *database -> models* (`_describe_modify`:
`db={old} models={new}` where `old` is the reflected connection type), so
`TYPE MISMATCH | alerts.payload | db=JSONB models=JSON` means the **database is
already JSONB** and `app/db/models.py` declares plain `sqlalchemy.JSON`. The DB
side is the better type; there is nothing to migrate.

Closing these is a *model* change, not a migration:
`JSON().with_variant(postgresql.JSONB(), "postgresql")` on the 10 columns
(agent_run_steps.input_data/output_data, alerts.payload, domain_events.payload,
failed_jobs.payload, feature_snapshots.features, forecast_logs.snapshot_metadata,
market_snapshots.metadata, model_versions.metrics, training_runs.metrics). Plain
`postgresql.JSONB` cannot be used directly because the rest of the suite builds
its schema on SQLite via `create_all`, where JSONB does not compile.

The charter restricted model edits to item 3 only, so this is **left in the
baseline and flagged for the orchestrator** rather than done unilaterally. The
recommended one-line-per-column fix is recorded in the regenerated baseline's
`_readme`.

## 3. `markets_slug_key` — adopted into the model (no DDL drop)

Evidence: revision 001 creates `sa.Column("slug", ..., unique=True)` **plus**
`op.create_index("ix_markets_slug", ...)`, i.e. a table-level UNIQUE constraint
named `markets_slug_key` and a separate non-unique index. The model declared
`unique=True, index=True` on the column, which SQLAlchemy renders as a single
unique *index* — so the harness reported the DDL constraint as "extra".

Slug uniqueness is semantically correct and is relied on across the catalog/sync
code, so the constraint is kept and the model is brought in line
(`__table_args__ = (UniqueConstraint("slug", name="markets_slug_key"),)`, column
now `nullable=False, index=True`). Uniqueness enforcement is unchanged in both
PostgreSQL (constraint) and the SQLite test schema (constraint instead of unique
index). This is the only model line touched.

## 4. Downgrade

`downgrade()` mirrors `upgrade()`: `DROP NOT NULL` for the same 63 columns in
reverse order. It is exercised for real — the `migrated_dsn` fixture runs
`upgrade head -> downgrade base -> upgrade head`.

## Verification — the migration WAS exercised

A local PostgreSQL on `localhost:5432` was available, so
`TEST_MIGRATION_DATABASE_URL` was set to a local admin DSN (never printed, never
committed) and the harness ran for real against a throwaway
`alphaedge_migtest_*` scratch database. No remote/production host was touched
(`TEST_MIGRATION_ALLOW_REMOTE_SCRATCH` was never set).

### `uv run alembic heads`

```
067_notnull_parity (head)
```

### `uv run --extra dev pytest tests/test_migration_exercise.py -q` (with scratch DSN)

```
...                                                                      [100%]
3 passed in 9.73s
```

Pre-regeneration run, showing the ratchet arithmetic:

```
[loop111] scratch database created: alphaedge_migtest_7a2e9b733919 on localhost:5432/postgres
[loop111] 63 baseline drift entries are now FIXED; shrink tests/migration_parity_baseline.json:
[loop111] model/DDL parity: 62 total drift entries, 125 baselined, 0 new
```

`0 new` = the migration and the model edit introduced no fresh drift.

### `uv run --extra dev ruff check app tests`

```
All checks passed!
```

### `uv run --extra dev pytest -q` (full backend suite)

```
2162 passed, 30 skipped in 492.96s (0:08:12)
```

## Guardrails

* `PAPER_TRADING_ONLY` untouched; no order-path change. 067 only tightens column
  nullability.
* Models changed only for item 3 (one class: `Market`).
* No secret printed, written, or committed. No push, no deploy, no `git add -A`.
* Files touched: `backend/alembic/versions/067_notnull_json_parity.py`,
  `backend/tests/migration_parity_baseline.json`,
  `backend/tests/test_migration_exercise.py` (baseline `_readme` text only),
  `backend/app/db/models.py` (Market slug/`__table_args__`), `STATE112-DRIFT.md`.

## Flag for the orchestrator

1. Re-exercise 067 against a production-shaped dump before deploy. The scratch
   run starts from an **empty** database, so the backfill `UPDATE`s were no-ops
   there; on real data they are what makes `SET NOT NULL` safe.
2. Decide on the 10 JSONB model declarations (section 2) — a separate, cheap,
   migration-free follow-up.
3. The 51 skipped columns need a per-column NULL count against prod before a
   follow-up ratchet loop.

AutoLab: baseline=125 baselined drift entries (loop111 harness, green) |
benchmark=`pytest tests/test_migration_exercise.py` entry count |
iterations=2 + best result 61 entries (-64) | budget=2/2 |
outcome=improved

## F1 fix (audit finding, AUDIT112-DRIFT.md)

Verdict was PASS WITH FINDINGS; single low-severity finding F1: `job_runs.started_at`
(`app/db/models.py:1222`) carries `server_default=func.now()` and therefore
qualifies under this loop's own safety rule, but it was left in the skip list —
a first-pass classification slip, not a deliberate exclusion. It is now the 63rd
entry in `NOT_NULL_FIXES` (`UPDATE "job_runs" SET "started_at" = now() WHERE
"started_at" IS NULL`, then `SET NOT NULL`; mirrored `DROP NOT NULL` in
`downgrade()`). The other two `job_runs` columns (`job_name`, `status`) have no
default and correctly remain skipped. Baseline 62 -> 61.

### `pytest tests/test_migration_exercise.py::test_model_ddl_parity -q -s` (before regeneration)

```
[loop111] scratch database created: alphaedge_migtest_b5399deda5a6 on localhost:5432/postgres
[loop111] 1 baseline drift entries are now FIXED; shrink tests/migration_parity_baseline.json:
  NULLABILITY MISMATCH | job_runs.started_at | db=True models=False
[loop111] model/DDL parity: 61 total drift entries, 62 baselined, 0 new
```

### `uv run --extra dev pytest tests/test_migration_exercise.py -q` (after regeneration)

```
...                                                                      [100%]
3 passed in 9.38s
```

### `uv run alembic heads`

```
067_notnull_parity (head)
```

### `uv run --extra dev ruff check app tests`

```
All checks passed!
```

### `uv run --extra dev pytest -q` (full backend suite, re-run after F1)

```
2162 passed, 30 skipped in 427.36s (0:07:07)
```
