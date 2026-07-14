# Loop V21 — STATE
| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| P1 | Index audit (+043 if needed) | DONE | Audit: `signal_events.created_at` MISSING; market-detail path already indexed (`markets.slug` unique/index, `ix_odds_snapshots_market_source_captured`). Migration **043** adds `ix_signal_events_created_at` only. Inspector proof: `tests/test_loop21_p1_indexes.py`. Gate: **1499 passed, 28 skipped** + ruff clean. |
| P2 | signals/feed TTL cache | DONE | `signal_feed_cache.py` (5s TTL, leaderboard pattern); `/signals/feed` success-only put; additive `cached` field. Tests hit/miss/expiry/error-not-cached. Gate: **1503 passed, 28 skipped** + ruff clean. |
| P3 | Retry-After on 429 | TODO | |
| P4 | Re-baseline vs V20 | TODO | |

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

## LOOP LOG
- 2026-07-14 P1 DONE | audit-only + 043 for created_at | pytest 1499 passed / 28 skipped | ruff clean | alembic heads=[043_signal_events_created_at_index]
- 2026-07-14 P2 DONE | signal_feed_cache 5s success-only | tests hit/miss/expiry/error-not-cached | pytest 1503 passed / 28 skipped | ruff clean

### ORCHESTRATOR REVIEW · P1 · 4992701 · verdict: PASS
Audit-first done right (no unnecessary index), 043 correctly chained, proof
test present, counts verified. Continue P2 → P3 → P4.

### ORCHESTRATOR REVIEW · P2 · 88a3827 · verdict: PASS
Leaderboard pattern followed, success-only, additive field, full test
quadrant. Continue P3 → P4.
