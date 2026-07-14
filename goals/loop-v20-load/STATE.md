# Loop V20 — STATE
| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| L1 | Harness + smoke | DONE | Locust harness under `loadtest/`; boot helper `scripts/boot_local_stack.py` (isolated SQLite + uvicorn on 127.0.0.1:18020, PAPER_TRADING_ONLY). Smoke: 20 VUs × 60s, exit 0, 0% fails. Evidence: `loadtest/results/smoke-20260714T153642Z.md` (+ CSV). Aggressive first run (`wait 0.1–0.5s`) hit global RATE_LIMIT 600/min → 43% 429 on markets (`smoke-20260714T153345Z`); smoke pacing set to 2.0–3.5s so harness validates happy path. |
| L2 | Read-path baseline | TODO | |
| L3 | Trade-path scenario | TODO | |
| L4 | Baseline report + PERF REPORTS | TODO | |

## PERF REPORTS (code findings — orchestrator routes; do not fix here)

## LOOP LOG
- 2026-07-14: L1 DONE — stack boot markets≈22, smoke p99 health≈45ms markets≈81ms @ 20 VU paced.
- Verifier: local only; `run_smoke.py` exit 0; host refused if non-loopback.

### ORCHESTRATOR REVIEW · L1 · 9f20489 · verdict: PASS
Scope perfect (loadtest/** only), isolated local stack, and a genuinely useful
first finding: the GLOBAL 600/min rate limit trips at ~20 aggressive VUs
(43% 429s) — good discovery, correctly documented rather than disabled.
Carry that into L3's 429-onset measurement. Continue L2 → L3 → L4.
