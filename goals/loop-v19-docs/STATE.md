# Loop V19 — STATE
| ID | Ticket | Status | Notes / verification evidence |
|----|--------|--------|------------------|
| W1 | API reference | DONE | `docs/api.md` — 111 table paths verified vs openapi_snapshot (131) + code; verifier PASS |
| W2 | User guide | DONE | `docs/user-guide.md` — UI routes + API wiring verified; equity/attribution API-only noted |
| W3 | Operations runbook | DONE | `docs/operations.md` — Railway path-as-root, env names, alembic head, monitoring |
| W4 | Model methodology | DONE | `docs/methodology.md` — XGB/calib/WF/CLV/leakage/drift/A-B no auto-activate |
| W5 | README refresh | DONE | root + backend/ + frontend/ READMEs; links W1–W4; Railway+Vercel; uv/docker/e2e |

## LOOP LOG (append per iteration; list endpoint/flag verifications)

### W1 — API reference (2026-07-14)

**Deliverable:** `docs/api.md`

**Verification evidence (each claim checked):**

| Claim | Verified via |
|-------|----------------|
| OpenAPI snapshot has 131 path keys (not nested under `paths`) | `backend/tests/fixtures/openapi_snapshot.json` JSON top-level keys |
| `GET /api/v1/markets` supports `sort=active` | `routes.py` `_VALID_SORTS = {"volume", "traders", "newest", "active"}` |
| Auth signup/login/logout/me/patch | `api/v1/auth.py`; cookie `ae_access` + Bearer in `deps.py` |
| Human paper `POST /api/v1/orders` + `Idempotency-Key` | `api/v1/orders.py` Header alias; dual-ledger docstring |
| Human close `POST /api/v1/positions/close` + Idempotency-Key | same file |
| CLOB place/cancel + RiskService | `routes.py` `place_order` / `cancel_order`; cancel 403/409/404 |
| Portfolio suite (summary/risk/attribution/equity-curve/exposure/clv) | `portfolio.py`, `portfolio_clv.py`; all JWT `get_current_user` |
| Leaderboard | `leaderboard.py` mounted under v1; `sort`/`limit`/`offset` |
| Activity trades + signals/events + alerts | `activity.py` |
| Watchlist JWT CRUD | `watchlist.py` |
| Eval evaluations/aggregates/calibration | `eval_routes.py` prefix `/api/v1/eval` |
| Drift under admin observability (not `/eval/drift`) | `observability.py` `/api/v1/admin/observability/drift` |
| System loops / metrics / resolved-count / model-ab | `system.py` |
| System sources admin | `sports.py` `sources_router` prefix `/api/v1/system` + `verify_admin_api_key` |
| WS `/api/v1/ws/feed` channels: briefs, alerts, feed, activity + bus topics | `ws.py` `_FEED_TOPICS`, `_BUS_TOPICS` |
| WS `/api/v1/ws/prices` | `ws.py` |
| Prometheus `/metrics` admin/token gated | `observability/metrics.py` |
| Admin markets/agents | `admin/routes.py`, `admin/agent_routes.py` |
| PAPER_TRADING_ONLY on trading + WS | `orders.py`, `ws.py` |
| No secret values in doc | manual review |

**Adversarial verifier:** `goals/loop-v19-docs/_verify_api_paths.py` → `table_paths=111` all found in snapshot or code → **PASS**. Explicitly confirmed fabricated `/api/v1/eval/drift` is **documented as non-existent**.

**Gate:** docs-only; relative links self-contained; no app code edits.

### W2 — User guide (2026-07-14)

**Deliverable:** `docs/user-guide.md`

**Verification evidence:**

| Claim | Verified via |
|-------|----------------|
| Signup → POST `/api/v1/auth/signup`, redirect `/portfolio` | `frontend/src/app/auth/signup/page.tsx` |
| Starting balance $100,000 | `User.paper_balance` default in `db/models.py`; `OnboardingModal` |
| Discover `/` uses `sort=active` | `app/page.tsx` `fetchMarkets({ sort: "active" })` |
| `/discover` redirects to `/` | `app/discover/page.tsx` |
| Trending filter (open, price 0.01–0.99, future end) | `live-discovery.ts` `activeTrendingMarkets` |
| Longshots/Decided → `/resolved` | `QuestDiscoverShell` Link href `/resolved` |
| Paper trade + Idempotency-Key | `orders-api.ts`, `MarketTradingPanel`, `POST /api/v1/orders` |
| Portfolio panels: clv/risk/exposure/profile | `portfolio/page.tsx` + `portfolio-api.ts` |
| Equity-curve + attribution APIs exist, **UI not wired** on portfolio | API in `portfolio.py`; no frontend callers for those paths |
| Equity chart on backtest only | `backtest/page.tsx` + `EquityCurveChart` |
| Leaderboard + demo fallback | `leaderboard/page.tsx` |
| Alerts notify-only | `alerts/page.tsx` comment + copy |
| Forecast lock LIVE only on OPEN; grade after resolve | `forecast_service.py` `lock_forecast`; `track_record.py` primary source |
| Thin/provisional track record | `track_record.py` `THIN_DATA_THRESHOLD`; UI PROVISIONAL badge |
| All 26 documented API paths in OpenAPI | adversarial script → missing NONE |
| All major frontend routes have `page.tsx` | `/`, auth, portfolio, signals, research, track-record, resolved, leaderboard, alerts, watchlist, trade, opportunities, feed, smart-money, backtest, markets |

**Adversarial verifier:** no fabricated endpoints; equity/attribution documented as API-only (not fake UI).

### W3 — Operations runbook (2026-07-14)

**Deliverable:** `docs/operations.md`

**Verification evidence:**

| Claim | Verified via |
|-------|----------------|
| Railway preDeploy alembic + uvicorn start + /health | `backend/railway.toml` |
| Worker start command | `backend/railway.worker.toml` |
| `railway up` from backend / `--path-as-root` | `scripts/deploy_railway.ps1`; `goals/build-loop-e2e/STATE.md` |
| Deploy script env names (no values) | `deploy_railway.ps1` variables list |
| PAPER_TRADING_ONLY required | `config.py` validator |
| Prod rejects default JWT/admin secrets | `config.py` `production_secrets_must_be_explicit` |
| Env field aliases | `config.py` Field aliases |
| Dual 017 merge → single head via 018 | `018_wc2026_tag.py` down_revision tuple |
| Head 040 | `040_portfolio_equity_snapshots.py` |
| demo-uptime cron + verify_prod + paper_trading_only assert | `.github/workflows/demo-uptime.yml` |
| Prometheus /metrics gated | `observability/metrics.py` |
| system/loops, sources, resolved-count | `system.py`, `sports.py` sources_router |
| Neon→Railway + rollback copy note | e2e STATE + deploy scripts (logical ops, no secrets) |
| 50 env tokens all known | `_verify_ops.py` PASS |
| Documented endpoints exist | `_verify_ops.py` missing apis NONE |

**Adversarial verifier:** PASS (no secret values; no invented endpoints).

### W4 — Model methodology (2026-07-14)

**Deliverable:** `docs/methodology.md`

**Verification evidence:**

| Claim | Verified via |
|-------|----------------|
| XGBoost default + optional LightGBM fallback | `model_registry.py`, `ML_MODEL_TYPE` |
| Calibrators Platt/isotonic/identity + ECE/Brier report | `calibration.py` |
| Walk-forward trainer | `trainer.py` `train_walk_forward_xgboost_*` |
| model_beats_closing = Brier+logloss vs closing | `backtesting/clv.py` |
| Predictor multi-gate edge | `forecasting/predictor.py` |
| Phase-3 blocked reasons | `backtesting/replay.py` |
| Leakage audit known_at ≤ decision_ts | `features.py` `assert_no_post_game_leakage` |
| Drift threshold 0.05, baseline 0.25, flag default off | `config.py` + `observability/drift.py` |
| A/B never flips model; MIN_RESOLVED_FOR_AB=100 | `ab_harness.py` |
| Nightly backtest flag-gated default off | `BACKTEST_NIGHTLY_ENABLED` |
| Eval/track-record/drift/model-ab endpoints in OpenAPI | all listed paths present |
| Paper-simulation disclaimer | doc header + PAPER_TRADING_ONLY |

**Adversarial verifier:** all code needles + OpenAPI paths OK; no fabricated auto-activation.

### W5 — README refresh (2026-07-14)

**Deliverable:** `README.md`, `backend/README.md`, `frontend/README.md`

**Verification evidence:**

| Claim | Verified via |
|-------|----------------|
| Links to docs/api, user-guide, operations, methodology | files exist; README table |
| Railway + Vercel as monitored stack | `demo-uptime.yml` BASE_URL/FRONTEND_URL pattern; operations doc |
| Quickstart: `uv sync`, docker compose, uvicorn, npm dev | `backend/pyproject.toml`, `docker-compose.yml`, package scripts |
| `npm run test:e2e` | `frontend/package.json` scripts `test:e2e` / `e2e` |
| Backend test cmds with uv | AGENTS.md + pyproject extras |
| PAPER_TRADING_ONLY prominent | README header + config validator (cross-ref) |
| No secret values | manual scan |
| backend/ + frontend/ README pointers | created, link to root docs |

**Adversarial verifier:** all README needles present; relative doc links resolve; no fabricated endpoints introduced.

### ORCHESTRATOR REVIEW · W1 · cf0faad · verdict: PASS
Spot-verified 5 documented surfaces against code independently — all real;
111/131 snapshot paths covered with verification table. Continue W2-W5.

### ORCHESTRATOR REVIEW · W2 · 63225de · verdict: PASS
Paper-only stated 21x, honest "how numbers accrue" present, API-only surfaces
flagged. Continue W3-W5.

### ORCHESTRATOR REVIEW · W3+W4+W5 · e0c5b5d, 9929f00, 3531d5a · verdict: PASS — LOOP V19 COMPLETE (5/5)
Independent checks: no secret values anywhere in docs (credential-substring
scan clean), env vars names-only, retrain never-auto-activates stated,
paper-simulation disclaimers present, deploy path matches reality. Lane
closed. Runner: STOP.
