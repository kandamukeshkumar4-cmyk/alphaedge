# STATE112 — AT-RISK cron dual-wire + retrain boot catch-up

Branch: `loop112-atrisk/node`
Worktree: `E:/polymarket-worktrees/loop112-atrisk`
Date: 2026-07-25

## What shipped

Priority-one fix + remaining safe AT-RISK dual-wires from `NOWRITER-SWEEP.md` §3,
mirroring `_whale_positions_loop` (boot catch-up before `while True`, `_paced_sleep`,
flag-gated, heartbeat ok+error, `LOOP_INTERVALS` registration).

| # | Task | Action |
|---|---|---|
| P1 | `refresh_whales_task` | **FIXED** sleep-first → boot catch-up + `_paced_sleep(604800)` |
| 1 | `snapshot_whale_positions_task` | already dual-wired (Loop111) |
| 2 | `model_retrain_task` | **WIRED** `_model_retrain_loop` (daily; task still `ML_RETRAIN_ENABLED=false`) |
| 3 | `nightly_backtest_task` | **WIRED** `_nightly_backtest_loop` (daily; task still `BACKTEST_NIGHTLY_ENABLED=false`) |
| 4 | `capture_market_snapshots_task` | **WIRED** `_market_snapshots_loop` (hourly) |
| 5 | `capture_historical_closing_snapshots_task` | **SKIPPED: admin-POST only (not an ARQ cron); manual capture stays on `/admin`** |
| 6 | `order_expiry_task` | **WIRED** `_order_expiry_loop` (60s; bounded batch via service) |
| 7 | `ingest_odds_task` | **SKIPPED: fixture CSV ingest would pollute prod `odds_snapshots`; live writers already wired** |
| 8 | `nightly_profile_refresh_task` / `fetch_news_signals_task` | **SKIPPED: profile is compute-only (no store); news cache warm superseded by wired `news_scan_task`** |

Also: `_generic_artifact_retrain_loop` boot catch-up guarded by
`_has_generic_artifact_retrain_this_week` (ModelVersion registry timestamps,
mirrors `_has_digest_today`). Weekly cadence unchanged; artifacts still INACTIVE.

## Files touched

- `backend/app/main.py` — loop blocks
- `backend/app/core/config.py` — scheduler flags
- `backend/app/observability/loop_state.py` — cadences
- `backend/tests/test_loop112_atrisk.py` — registration/wall-clock + retrain boot tests
- `STATE112.md` — this file

## Guardrails

- `PAPER_TRADING_ONLY` untouched
- No new order-path imports in charter code (expiry loop calls existing task)
- No LLM calls added; zero migrations; no secrets; no push/deploy

## AutoLab

AutoLab: not applicable (no iterative measure) — wiring/reachability fix

---

## STOP — verification (verbatim)

### targeted pytest

```text
$ cd backend && uv run --extra dev pytest -q tests/test_loop112_atrisk.py
........                                                                 [100%]
8 passed in 10.10s
```

### ruff

```text
$ cd backend && uv run --extra dev ruff check app tests
All checks passed!
```

### alembic heads (066)

```text
$ cd backend && uv run --extra dev alembic heads
066_alpha_validation (head)
```

### full suite summary

```text
$ cd backend && uv run --extra dev pytest -q
2170 passed, 30 skipped in 474.10s (0:07:54)
```
