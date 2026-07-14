# Loop V20 — STATE
| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| L1 | Harness + smoke | DONE | Locust harness under `loadtest/`; boot helper `scripts/boot_local_stack.py` (isolated SQLite + uvicorn on 127.0.0.1:18020, PAPER_TRADING_ONLY). Smoke: 20 VUs × 60s, exit 0, 0% fails. Evidence: `loadtest/results/smoke-20260714T153642Z.md` (+ CSV). Aggressive first run (`wait 0.1–0.5s`) hit global RATE_LIMIT 600/min → 43% 429 on markets (`smoke-20260714T153345Z`); smoke pacing set to 2.0–3.5s so harness validates happy path. |
| L2 | Read-path baseline | DONE | 15 VUs × 120s, exit 0, 0% fails. Evidence: `loadtest/results/baseline-2026-07-14.md` + `readpath-20260714T153900Z_*.csv`. Endpoints: markets (default + sort=active), detail, slug, candles, signals, signals/feed, leaderboard, feed, portfolio + summary (authed). p99>1s on markets/{slug} (~2s), portfolio (~1.4s), signals/feed (~2.1s); signup setup p99~5.3s (setup-only). |
| L3 | Trade-path scenario | DONE | 5 VUs × 90s buy/close cycle, exit 0, **0 fails / 0 5xx**. Evidence: `loadtest/results/trade-20260714T154227Z.md`. 429 onset probe (single-token hammer POST /api/v1/orders): **first 429 at attempt 583** after **26.4s** (582×201 then 1×429); five_xx=0; Retry-After null on observed 429 (consistent with global slowapi 600/min bucket exhaustion ~600 reqs). Mutating limit also 600/min — not disabled. |
| L4 | Baseline report + PERF REPORTS | DONE | Report: `loadtest/results/PERF-BASELINE.md`. One-command: `py -3.13 loadtest/scripts/run_all.py`. PERF REPORTS below for all product endpoints with p99>1s. No backend/frontend code edits. |

## PERF REPORTS (code findings — orchestrator routes; do not fix here)

### PERF-01 — `GET /api/v1/signals/feed` p99 ≈ 2100 ms (p50 8 ms)
- **Evidence**: L2 `readpath-20260714T153900Z` — 70 reqs, 0 fails, p50=8 p95=51 p99=2100.
- **Code**: `backend/app/api/v1/routes.py` → `list_signal_feed` / `get_signal_feed` → `CLVTrackingService.get_signal_feed` (`forecast_dashboard_service.py`) simple `SELECT SignalEvent ORDER BY created_at DESC LIMIT n`.
- **Suspected cause**: Tail latency under multi-VU SQLite contention (shared with concurrent signup bcrypt), not query complexity. Median healthy.
- **Suggested owner loop**: backend perf / data-access (index on `signal_events.created_at` if missing; optional short TTL cache like markets list).

### PERF-02 — `GET /api/v1/markets/{slug}` p99 ≈ 2000 ms (p50 9 ms)
- **Evidence**: L2 — 46 reqs, 0 fails, p50=9 p95=120 p99=2000.
- **Code**: `MarketService.get_public_market_by_slug` with correlated `_latest_yes_price_subquery` on `OddsSnapshot` (`market_service.py`). List endpoint uses `markets_cache` (3s TTL); **single-slug path is uncached**.
- **Suspected cause**: Uncached slug lookup + OddsSnapshot subquery; SQLite lock tail under concurrent load. Compare: `/markets` p99=81 ms (cached).
- **Suggested owner loop**: backend markets (extend cache key to slug, or denormalize latest yes_price on Market row).

### PERF-03 — `GET /api/v1/portfolio` p99 ≈ 1400 ms (p50 9 ms)
- **Evidence**: L2 — 66 reqs, 0 fails, p50=9 p95=53 p99=1400.
- **Code**: `portfolio.py` `get_portfolio` → `_load_paper_orders` + `_latest_implied_yes_by_slug` for open slugs.
- **Suspected cause**: Empty/new-user portfolios should be light; p99 tail aligns with ramp contention (same window as multi-VU signup). Worth single-VU isolation remeasure before optimizing.
- **Suggested owner loop**: backend portfolio (batch implied prices; ensure indexes on `paper_orders.user_id`).

### PERF-04 (setup-only, not product read) — `POST /api/v1/auth/signup` p99 ≈ 5300 ms
- **Evidence**: L2 setup row — 15 signups, p50=3100 p99=5300.
- **Code**: `security.hash_password` → `bcrypt.gensalt()` + `hashpw` (intentional cost).
- **Suspected cause**: bcrypt work factor; expected. Blocks event loop if not offloaded under high concurrent signup (locust ramp of 15 VUs each hashing once).
- **Suggested owner loop**: backend auth only if concurrent signup is a product path (run bcrypt in threadpool). **Not a read-path regression.**

## LOOP LOG
- 2026-07-14: L1 DONE — smoke p99 health≈45ms markets≈81ms @ 20 VU paced. Commit `perf(loop20): L1 harness + smoke`.
- 2026-07-14: L2 DONE — read-path baseline 777 reqs / 0 fails. Commit `perf(loop20): L2 read-path baseline`.
- 2026-07-14: L3 DONE — trade cycle 141 reqs / 0 fails; 429 onset @583. Commit `perf(loop20): L3 trade-path + 429 onset`.
- 2026-07-14: L4 DONE — PERF-BASELINE.md + PERF-01..04 + `run_all.py`. Verifier: local-only, no backend/frontend edits; tickets L1–L4 DONE.
