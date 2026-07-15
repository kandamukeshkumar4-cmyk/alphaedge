# Loop V32 — STATE
| ID | Ticket | Status | Notes |
|----|--------|--------|-------|
| T1 | Coverage baseline | DONE | 1,572 passed, 28 skipped; 17,023/20,772 lines (82.0% line; 78.5% combined branch coverage). |
| T2 | Money paths | DONE | Added 5 behavior cases for rejected order rollback, empty-book market failure, NO fills, and risk-boundary expiry. |
| T3 | Auth + resolution paths | DONE | Added leakage-at-close, terminal-VOID, double-resolve, and staging-cookie behavior coverage. |
| T4 | Re-measure + gate | DONE | 1,581 passed / 28 skipped; 82.1% line coverage; ruff, fresh verifier, and deterministic gate PASS. |

## BUG REPORTS (app defects found — do not fix here)

## T1 BASELINE — 2026-07-15

Command: `$env:ADMIN_API_KEY='dev-admin-key'; uv run --extra dev pytest -q -p no:cacheprovider --cov=app --cov-branch --cov-report=json:coverage-baseline.json`

`pytest-cov>=6.0` was absent from the `dev` extra and was added; no test files changed. The table is ranked by line coverage (not the combined branch metric):

| Module | Covered lines | Line coverage |
|---|---:|---:|
| app/workers/main.py | 0/4 | 0.0% |
| app/backtesting/__init__.py | 2/6 | 33.3% |
| app/api/v1/market_candles.py | 31/76 | 40.8% |
| app/services/signal_event_seed.py | 8/19 | 42.1% |
| app/api/v1/calibration.py | 45/100 | 45.0% |
| app/workers/tasks.py | 244/509 | 47.9% |
| app/data/streams/runner.py | 42/86 | 48.8% |
| app/api/v1/orders.py | 65/130 | 50.0% |
| app/services/paper_account_service.py | 35/69 | 50.7% |
| app/api/v1/admin_markets.py | 86/166 | 51.8% |
| app/main.py | 240/459 | 52.3% |
| app/api/v1/briefs.py | 70/126 | 55.6% |
| app/api/v1/opportunities.py | 47/83 | 56.6% |
| app/data/fifa/predictor.py | 89/155 | 57.4% |
| app/api/v1/portfolio.py | 86/149 | 57.7% |
| app/api/v1/edge_history.py | 30/51 | 58.8% |
| app/api/v1/backtest.py | 163/276 | 59.1% |
| app/api/v1/market_drivers.py | 35/59 | 59.3% |
| app/signals/news_fetcher.py | 88/148 | 59.5% |
| app/api/v1/clones.py | 71/118 | 60.2% |

T2 target selection remains constrained to money paths. Among those, `app/api/v1/orders.py` (50.0%) and `app/services/order_book_service.py` (87.1% line; critical branch gaps) warrant behavior-focused cases; existing `ledger_service.py`, `settlement_service.py`, and `risk/rules.py` already have higher line coverage but retain meaningful failure/edge branches.

## T2 MONEY PATHS — 2026-07-15

Added `backend/tests/test_loop32_money_paths.py` with five behavior cases:

- limit-order failures (missing price and expired order) leave no persisted order, reserved cash, or balance mutation;
- a market order against an empty book leaves no order, ledger entry, or balance mutation;
- a crossed NO fill creates opposite NO positions and balanced trade ledger amounts; and
- exact `RiskService` thresholds (5% edge, 0.70 confidence, 5% bankroll cap, five-minute cutoff) pass, while an expired order fails only its expiry rule.

Focused money-path proof: `40 passed in 22.72s` for the new suite plus order-book, settlement, risk, and idempotency regressions. No application defect was found.

## T3 AUTH + RESOLUTION PATHS — 2026-07-15

Added `backend/tests/test_loop32_resolution_security.py` with four behavior cases:

- a LIVE forecast locked exactly at `resolved_at` is excluded from scoring (strictly pre-resolution only);
- a terminal venue response without an unambiguous outcome (VOID) remains OPEN and creates no score;
- a second direct external-market resolution is rejected and cannot overwrite the first outcome or timestamp; and
- staging access-cookie creation and deletion both retain `Secure`, `HttpOnly`, and `SameSite=Lax` attributes.

Focused auth/resolution proof: `53 passed in 15.68s` across the new suite plus external resolver/scoring, auto-lock, forecast mirror, and auth/cookie regressions. No application defect was found.

## T4 RE-MEASURE + GATE — 2026-07-15

| Coverage target | Before (T1) | After (T4) | Delta |
|---|---:|---:|---:|
| `backend/app` total line coverage | 17,023/20,772 (82.0%) | 17,034/20,772 (82.1%) | +11 lines / +0.1 pp |
| `services/order_book_service.py` | 209/240 (87.1%) | 219/240 (91.3%) | +10 lines / +4.2 pp |
| `services/external_market_service.py` | 70/96 (72.9%) | 71/96 (74.0%) | +1 line / +1.1 pp |
| `services/ledger_service.py` | 32/34 (94.1%) | 32/34 (94.1%) | behavior/branch hardening |
| `services/settlement_service.py` | 76/82 (92.7%) | 76/82 (92.7%) | behavior/branch hardening |
| `risk/rules.py` | 93/100 (93.0%) | 93/100 (93.0%) | boundary hardening |
| `services/external_market_resolver.py` | 32/43 (74.4%) | 32/43 (74.4%) | terminal-VOID proof |
| `services/scoring_service.py` | 44/46 (95.7%) | 44/46 (95.7%) | exact-close leakage proof |
| `services/forecast_service.py` | 81/88 (92.0%) | 81/88 (92.0%) | existing lock behavior retained |

Final measurement: `$env:ADMIN_API_KEY='dev-admin-key'; uv run --extra dev pytest -q -p no:cacheprovider --cov=app --cov-branch` -> `1581 passed, 28 skipped`; terminal combined coverage rounded to `79%` (T1 JSON was 78.5%).

Task gate: `$env:ADMIN_API_KEY='dev-admin-key'; uv run --extra dev pytest -q -p no:cacheprovider` -> `1581 passed, 28 skipped in 241.93s`; `uv run --extra dev ruff check app tests` -> `All checks passed!`.

Fresh verifier: **PASS** — independently ran the same full backend test and ruff commands, inspected `42ea761..HEAD`, found only the five scoped files, and found no application or forbidden-test edits. The only test-process noise is the post-exit Windows temporary-directory cleanup warning; all test commands exited 0.

Deterministic gate: `py -3.13 orchestration/gate.py` -> `PASS: all checks green` (backend 1,581/28, ruff, frontend typecheck, 381 frontend tests, and frontend build). The first invocation was environment-blocked by absent `frontend/node_modules`; `npm ci` from the existing lockfile restored dependencies without changing a manifest, and the rerun passed.

Remaining gaps: low coverage remains in worker entrypoints, network/external-provider clients, and broad API routes outside this tests-only ticket. Order-book concurrent `IntegrityError` recovery and notification-failure paths remain difficult to force deterministically without mocking internal transaction boundaries; no production code was changed to make them testable.

AutoLab: baseline=1,572 passed / 28 skipped, 82.0% line | benchmark=full backend coverage plus gates | iterations=2 behavior-test slices + best 82.1% line | budget=2/2 | outcome=improved

## LOOP LOG

loop-v32 | 2026-07-15 | T1 DONE | baseline full suite: 1,572 passed, 28 skipped, 82.0% line / 78.5% combined; pytest-cov added to dev extra
loop-v32 | 2026-07-15 | T2 DONE | 5 money-path behavior cases; focused regression set 40 passed
loop-v32 | 2026-07-15 | T3 DONE | 4 auth/resolution behavior cases; focused regression set 53 passed
loop-v32 | 2026-07-15 | T4 DONE | 1,581 passed / 28 skipped, 82.1% line; verifier PASS; deterministic gate PASS
