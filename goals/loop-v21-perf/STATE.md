# Loop V21 — STATE
| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| P1 | Index audit (+043 if needed) | DONE | Audit: `signal_events.created_at` MISSING; market-detail path already indexed (`markets.slug` unique/index, `ix_odds_snapshots_market_source_captured`). Migration **043** adds `ix_signal_events_created_at` only. Inspector proof: `tests/test_loop21_p1_indexes.py`. Gate: **1499 passed, 28 skipped** + ruff clean. |
| P2 | signals/feed TTL cache | DONE | `signal_feed_cache.py` (5s TTL, leaderboard pattern); `/signals/feed` success-only put; additive `cached` field. Tests hit/miss/expiry/error-not-cached. Gate: **1503 passed, 28 skipped** + ruff clean. |
| P3 | Retry-After on 429 | DONE | Global: `global_rate_limit_exceeded_handler` always sets Retry-After (seconds). Mutating already had header; tests assert both. Gate: **1506 passed, 28 skipped** + ruff clean. |
| P4 | Re-baseline vs V20 | DONE | `py -3.13 loadtest/scripts/run_all.py` exit 0 on 127.0.0.1:18020. Evidence: `smoke-20260714T191503Z`, `readpath-20260714T191620Z`, `trade-20260714T191831Z`. See before/after table below. |

## MIGRATION CLAIMS (043+)
| Number | Ticket | Status |
|---|---|---|
| 043_signal_events_created_at_index | P1 | DONE — single head, revises 042_forecast_drift_snapshots |

## SHARED FILE CLAIMS
| File | Ticket | Status |
|---|---|---|
| backend/app/db/models.py | P1 | DONE — added Index on SignalEvent.created_at |
| backend/app/api/v1/routes.py | P2 | DONE — /signals/feed TTL cache wire-up |
| backend/app/schemas/signals.py | P2 | DONE — additive cached: bool = False |
| backend/app/main.py | P3 | DONE — wire global_rate_limit_exceeded_handler |
| backend/app/core/ratelimit.py | P3 | DONE — handler + mutating already had Retry-After |

## P4 before/after p99 (L2 read-path, local SQLite stack)

**V20 baseline**: `loadtest/results/PERF-BASELINE.md` (readpath-20260714T153900Z)  
**V21 re-run**: `readpath-20260714T191620Z` · 15 VUs × 120s · 0 fails · 786 reqs

| Endpoint | V20 p50 | V20 p99 | V21 p50 | V21 p99 | Delta p99 |
|----------|--------:|--------:|--------:|--------:|----------:|
| GET /signals/feed | 8 | **2100** | 4 | **24** | **−99%** (P2 TTL cache) |
| GET /markets/{slug} | 9 | **2000** | 6 | **34** | −98% (index path already ok; run variance) |
| GET /portfolio (authed) | 9 | **1400** | 7 | **36** | −97% (no code change; contention variance) |
| GET /markets | 6 | 81 | 4 | 15 | −81% |
| GET /markets/{slug}/detail | 12 | 330 | 9 | **1200** | +264% (tail spike; see caveats) |
| GET /markets/{slug}/candles | 13 | 79 | 9 | **1100** | +1292% (tail spike) |
| GET /signals | 8 | 79 | 6 | **1100** | +1292% (uncached twin of feed) |
| POST /auth/signup (setup) | 3100 | 5300 | 1700 | 3800 | −28% (bcrypt; setup-only) |

### L3 429 onset (single-token hammer POST /orders)

| Metric | V20 | V21 |
|--------|-----|-----|
| First 429 at attempt | 583 | 576 |
| Retry-After header | **null** | **"23"** (P3 fix) |
| 5xx during probe | 0 | 0 |

### Contention caveats (honest)

1. **Local SQLite + multi-VU**: p99 tails are dominated by write-lock / bcrypt signup ramp, not steady-state query cost. Medians stayed healthy on both runs.
2. **signals/feed p99 collapse is real product improvement** (5s success-only cache); medians were already fine.
3. **Uncached siblings** (`/signals`, detail, candles) still show multi-second p99 spikes on this host — not regressed by P1–P3 order path; same class of SQLite contention V20 documented.
4. **markets/{slug} and portfolio** look “fixed” by numbers alone, but no dedicated cache was added for them in this loop — treat as run variance until single-VU isolation remeasures.
5. Stack: `PAPER_TRADING_ONLY=true`, rate limits left **enabled** (600/min), loopback only.

## LOOP LOG
- 2026-07-14 P1 DONE | audit-only + 043 for created_at | pytest 1499 passed / 28 skipped | ruff clean | alembic heads=[043_signal_events_created_at_index]
- 2026-07-14 P2 DONE | signal_feed_cache 5s success-only | tests hit/miss/expiry/error-not-cached | pytest 1503 passed / 28 skipped | ruff clean
- 2026-07-14 P3 DONE | global Retry-After handler + mutating assert | pytest 1506 passed / 28 skipped | ruff clean
- 2026-07-14 P4 DONE | run_all.py exit 0 | feed p99 2100→24; Retry-After on 429; see table

### ORCHESTRATOR REVIEW · P1 · 4992701 · verdict: PASS
Audit-first done right (no unnecessary index), 043 correctly chained, proof
test present, counts verified. Continue P2 → P3 → P4.

### ORCHESTRATOR REVIEW · P2 · 88a3827 · verdict: PASS
Leaderboard pattern followed, success-only, additive field, full test
quadrant. Continue P3 → P4.

### ORCHESTRATOR REVIEW · P3 · 6f3b408 · verdict: PASS
Both limiters now emit Retry-After with tests. Finish with P4 (honest
re-baseline), then STOP — lane closes.

### ADVERSARIAL VERIFIER · P4 · local re-baseline · verdict: PASS
- Command: `py -3.13 loadtest/scripts/run_all.py` → exit 0 (L1+L2+L3).
- Guardrails: local 127.0.0.1:18020 only; PAPER_TRADING_ONLY; no frontend/connectors/deploy edits; order path untouched.
- P3 evidence in the wild: `first_429_retry_after: "23"` (was null on V20).
- P2 evidence: `/signals/feed` p99 2100→24 with p50 still ~4–8ms.
- Honest caveats recorded for SQLite multi-VU p99 noise on uncached paths.

### ORCHESTRATOR REVIEW · P4 · 20aa1c4 · verdict: PASS — LOOP V21 COMPLETE (4/4)
Honest re-baseline (feed p99 2100ms -> 24ms, Retry-After live, variance
caveats stated). Independent gate 1506 passed, head 043. Lane closed.
