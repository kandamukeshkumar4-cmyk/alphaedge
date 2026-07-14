# PERF-BASELINE — Loop V20 (local stack)

**Date**: 2026-07-14  
**Host**: `http://127.0.0.1:18020` only (never Railway/Vercel)  
**Stack**: isolated SQLite + uvicorn, `PAPER_TRADING_ONLY=true`, schedulers off  
**Tool**: Locust 2.45 via `uv run --with locust`  
**One-command re-run**: `py -3.13 loadtest/scripts/run_all.py`

## Environment

| Item | Value |
|------|--------|
| API port | 18020 |
| DB | `loadtest/.data/loop20.sqlite3` (ephemeral per boot) |
| Seed markets | ≈22 after boot |
| Global rate limit | `RATE_LIMIT=600/minute` (slowapi, per IP) |
| Mutating rate limit | `RATE_LIMIT_MUTATING=600/minute` (per token+path; left enabled) |

## Summary tables

### L1 Smoke — 20 VUs × 60s (paced wait 2.0–3.5s)

Source: `smoke-20260714T153642Z_stats.csv`

| Endpoint | #reqs | fails | p50 ms | p95 ms | p99 ms | avg ms |
|----------|------:|------:|-------:|-------:|-------:|-------:|
| GET /health | 125 | 0 | 4 | 11 | 45 | 6 |
| GET /api/v1/markets | 307 | 0 | 5 | 31 | 81 | 8 |
| Aggregated | 432 | 0 | 5 | 31 | 80 | 8 |

**Note**: Aggressive smoke (`wait 0.1–0.5s`, `smoke-20260714T153345Z`) produced **43.8% 429** on markets under the global 600/min IP limit — harness works; pacing documents honest rate-limit behavior.

### L2 Read-path — 15 VUs × 120s

Source: `baseline-2026-07-14.md` / `readpath-20260714T153900Z_stats.csv`

| Endpoint | #reqs | fails | err% | p50 ms | p95 ms | p99 ms | avg ms |
|----------|------:|------:|-----:|-------:|-------:|-------:|-------:|
| GET /api/v1/markets | 121 | 0 | 0 | 6 | 46 | 81 | 11 |
| GET /api/v1/markets?sort=active | 91 | 0 | 0 | 7 | 37 | 130 | 11 |
| GET /api/v1/markets/{slug} | 46 | 0 | 0 | 9 | 120 | **2000** | 64 |
| GET /api/v1/markets/{slug}/detail | 84 | 0 | 0 | 12 | 53 | 330 | 20 |
| GET /api/v1/markets/{slug}/candles | 84 | 0 | 0 | 13 | 34 | 79 | 16 |
| GET /api/v1/signals | 55 | 0 | 0 | 8 | 76 | 79 | 15 |
| GET /api/v1/signals/feed | 70 | 0 | 0 | 8 | 51 | **2100** | 48 |
| GET /api/v1/leaderboard | 71 | 0 | 0 | 6 | 60 | 170 | 12 |
| GET /api/v1/feed | 53 | 0 | 0 | 15 | 55 | 200 | 23 |
| GET /api/v1/portfolio (authed) | 66 | 0 | 0 | 9 | 53 | **1400** | 36 |
| GET /api/v1/portfolio/summary (authed) | 21 | 0 | 0 | 9 | 24 | 63 | 13 |
| POST /api/v1/auth/signup (setup) | 15 | 0 | 0 | 3100 | 5300 | **5300** | 3386 |
| Aggregated | 777 | 0 | 0 | 9 | 76 | 3100 | 88 |

### L3 Trade-path — 5 VUs × 90s + 429 onset

Source: `trade-20260714T154227Z.md`

| Endpoint | #reqs | fails | p50 ms | p95 ms | p99 ms | avg ms |
|----------|------:|------:|-------:|-------:|-------:|-------:|
| POST /api/v1/orders (buy) | 68 | 0 | 27 | 160 | 650 | 51 |
| POST /api/v1/positions/close | 41 | 0 | 32 | 140 | 770 | 62 |
| GET /api/v1/portfolio (trade cycle) | 27 | 0 | 12 | 23 | 26 | 13 |
| POST /api/v1/auth/signup (setup) | 5 | 0 | 500 | 570 | 570 | 467 |
| Aggregated | 141 | 0 | 27 | 270 | 650 | 61 |

**5xx**: **0** (locust + onset probe).

**429 onset** (single bearer token, hammer `POST /api/v1/orders`):

| Metric | Value |
|--------|--------|
| First 429 at attempt | **583** |
| Elapsed to first 429 | **26.4 s** |
| Prior successes | 582 × HTTP 201 |
| 5xx during probe | 0 |
| Retry-After header | null (observed; likely global slowapi path) |
| Config defaults | global `600/minute` IP + mutating `600/minute` token+path |

## Top-3 slowest product endpoints (by p99, L2)

| Rank | Endpoint | p50 | p99 | Suspected cause (code read; not fixed here) |
|-----:|----------|----:|----:|-----------------------------------------------|
| 1 | `GET /api/v1/signals/feed` | 8 ms | 2100 ms | Thin wrapper over `CLVTrackingService.get_signal_feed` → `SELECT SignalEvent ORDER BY created_at DESC LIMIT n`. Median is fine; p99 tail likely SQLite write-lock / concurrent contention with signup bcrypt bursts at ramp, not algorithmic N+1. Confirm with EXPLAIN + single-VU remeasure. |
| 2 | `GET /api/v1/markets/{slug}` | 9 ms | 2000 ms | `MarketService.get_public_market_by_slug` joins `Market` + correlated subquery `_latest_yes_price_subquery` on `OddsSnapshot` (`ORDER BY captured_at DESC LIMIT 1` per market). List path is cached (`markets_cache` 3s TTL); single-slug path is **uncached**. Tail spikes under multi-VU SQLite. |
| 3 | `GET /api/v1/portfolio` | 9 ms | 1400 ms | Loads all paper orders for user (`_load_paper_orders`) then `_latest_implied_yes_by_slug` for open slugs. Empty portfolios should be cheap; tail again concurrent with signup/hash load on shared SQLite file. |

**Honorable mention (setup only)**: `POST /api/v1/auth/signup` p50≈3.1s / p99≈5.3s during L2 ramp — `bcrypt.gensalt()` + `hashpw` is intentionally expensive (`app/core/security.py`). Not a product read path; still dominates aggregate p99 when mixed into the scenario.

## Rate-limit behavior (honest)

1. **Global read path**: 20 VUs with sub-second wait → markets **429** (~44% fail rate in aggressive smoke).
2. **Mutating / global write path**: single-token hammer → **429 at ~583 requests / ~26s**, matching ~600/min budget.
3. Limits were **not** disabled for testing.

## How to reproduce

```powershell
# Full L1→L3 (writes fresh results/; does not rewrite this file unless --write-baseline)
py -3.13 loadtest/scripts/run_all.py

# Individual tickets
py -3.13 loadtest/scripts/run_smoke.py
py -3.13 loadtest/scripts/run_read_path.py
py -3.13 loadtest/scripts/run_trade_path.py

# Stack only
py -3.13 loadtest/scripts/boot_local_stack.py --check
```

## Guardrails confirmed

- [x] Local loopback only (`scenarios/common.py` refuses non-local hosts)
- [x] `PAPER_TRADING_ONLY=true` required on health
- [x] No edits under `backend/**` or `frontend/**`
- [x] PERF REPORTS for p99 > 1s filed in `goals/loop-v20-load/STATE.md`
