# Loop V20 — STATE
| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| L1 | Harness + smoke | DONE | Locust harness under `loadtest/`; boot helper `scripts/boot_local_stack.py` (isolated SQLite + uvicorn on 127.0.0.1:18020, PAPER_TRADING_ONLY). Smoke: 20 VUs × 60s, exit 0, 0% fails. Evidence: `loadtest/results/smoke-20260714T153642Z.md` (+ CSV). Aggressive first run (`wait 0.1–0.5s`) hit global RATE_LIMIT 600/min → 43% 429 on markets (`smoke-20260714T153345Z`); smoke pacing set to 2.0–3.5s so harness validates happy path. |
| L2 | Read-path baseline | DONE | 15 VUs × 120s, exit 0, 0% fails. Evidence: `loadtest/results/baseline-2026-07-14.md` + `readpath-20260714T153900Z_*.csv`. Endpoints: markets (default + sort=active), detail, slug, candles, signals, signals/feed, leaderboard, feed, portfolio + summary (authed). p99>1s on markets/{slug} (~2s), portfolio (~1.4s), signals/feed (~2.1s); signup setup p99~5.3s (setup-only). |
| L3 | Trade-path scenario | DONE | 5 VUs × 90s buy/close cycle, exit 0, **0 fails / 0 5xx**. Evidence: `loadtest/results/trade-20260714T154227Z.md`. 429 onset probe (single-token hammer POST /api/v1/orders): **first 429 at attempt 583** after **26.4s** (582×201 then 1×429); five_xx=0; Retry-After null on observed 429 (consistent with global slowapi 600/min bucket exhaustion ~600 reqs). Mutating limit also 600/min — not disabled. |
| L4 | Baseline report + PERF REPORTS | TODO | |

## PERF REPORTS (code findings — orchestrator routes; do not fix here)
(deferred to L4 — candidates measured in L2)

## LOOP LOG
- 2026-07-14: L1 DONE — smoke p99 health≈45ms markets≈81ms @ 20 VU paced. Commit `perf(loop20): L1 harness + smoke`.
- 2026-07-14: L2 DONE — read-path baseline 777 reqs / 0 fails. Commit `perf(loop20): L2 read-path baseline`.
- 2026-07-14: L3 DONE — trade cycle 141 reqs / 0 fails; 429 onset @583. Verifier: `run_trade_path.py` exit 0.
