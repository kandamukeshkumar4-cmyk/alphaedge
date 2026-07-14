# AlphaEdge API reference

> **Paper-trading only.** AlphaEdge is a prediction-market **simulation**. All
> balances, orders, fills, and P&L use simulated funds. The process requires
> `PAPER_TRADING_ONLY=true`. Human JWT paper orders and the agent CLOB path both
> refuse to run when that flag is false.

This document describes the **public and admin HTTP/WebSocket surface as
implemented in code**, derived from `backend/app/**` and
`backend/tests/fixtures/openapi_snapshot.json` (131 path keys). It is not a
marketing surface: if an endpoint is not listed here, do not assume it exists.

Interactive OpenAPI UI (when the API is running): `GET /docs` (Swagger) and
`GET /redoc`. Machine-readable schema: `GET /openapi.json`.

Base path for most application APIs: **`/api/v1`**.

---

## Conventions

| Topic | Behavior |
|-------|----------|
| Auth (human UI) | JWT Bearer `Authorization: Bearer <token>` **or** httpOnly cookie `ae_access` (Bearer wins if both present). See `app/api/v1/deps.py`. |
| Auth (admin) | Header `X-Admin-API-Key` (compared to `ADMIN_API_KEY`). See `verify_admin_api_key`. |
| Auth (agent CLOB account) | Header `X-Paper-Account-Token` for account-scoped CLOB actions. Tokenless access to shared system/smoke accounts is allowed only when `APP_ENV` is not `prod`/`production`/`staging`. |
| Idempotency | Optional header `Idempotency-Key` (max 64 chars) on paper open/close and CLOB place. |
| Paper disclaimer | Many responses include `paper_trading_only: true` or a disclaimer string. |
| Rate limits | Global SlowAPI limit (`RATE_LIMIT` setting) plus mutating-path middleware; valid admin key is exempt. |
| Request IDs | `X-Request-ID` on responses via `RequestIdMiddleware`. |

### Two paper-trading ledgers (do not conflate)

| Path | Ledger | Gate | Primary consumers |
|------|--------|------|-------------------|
| `POST /api/v1/orders`, `POST /api/v1/positions/close` | JWT user `PaperOrder` + `users.paper_balance` | `PAPER_TRADING_ONLY`, balance, open-market, price tolerance | Human UI |
| `POST /api/v1/markets/{slug}/orders`, `POST /api/v1/orders/{order_id}/cancel` | CLOB `orders`/`fills` + ledger | `RiskService` → `OrderIntent` → `OrderBookService` | Agents / smoke / paper accounts |

Source: module docstring in `backend/app/api/v1/orders.py`.

---

## System & health

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `GET` | `/` | Public | API root. |
| `GET` | `/health` | Public | Liveness; reports paper-trading posture. |
| `GET` | `/api/v1/health/detailed` | Public | Detailed health. |
| `GET` | `/metrics` | **Admin or `METRICS_TOKEN`** | Prometheus text exposition. Requires `X-Admin-API-Key` **or** `Authorization: Bearer <METRICS_TOKEN>`. |
| `GET` | `/api/v1/system/metrics` | Public | In-process HTTP/cache counters (not Prometheus format). |
| `GET` | `/api/v1/system/loops` | Public | Background loop plan + heartbeats (`price_feed`, `live_ingest`, `eval`, venue WS, schedulers, …). |
| `GET` | `/api/v1/system/sources` | **Admin** | Per-connector health registry (`sources_router` dependencies). |
| `GET` | `/api/v1/system/resolved-count` | Public | Resolved outcome count vs A/B threshold; never flips the default model. |
| `GET` | `/api/v1/system/model-ab` | Public | Walk-forward LightGBM vs XGBoost readout; `applied` is always false. |

---

## Auth (`/api/v1/auth`)

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `POST` | `/api/v1/auth/signup` | Public | Body: email + password. `201` + `access_token`; also sets `ae_access` cookie. `409` if email registered. |
| `POST` | `/api/v1/auth/login` | Public | Same token+cookie pattern. `401` on bad credentials. |
| `POST` | `/api/v1/auth/logout` | Public | Clears cookie; `204`. Bearer clients drop the token client-side. |
| `GET` | `/api/v1/auth/me` | JWT | Profile: `id`, `email`, `paper_balance`, `created_at`. |
| `PATCH` | `/api/v1/auth/me` | JWT | Optional `onboarded`, `display_name` (≤32 chars). |

---

## Markets & discovery

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `GET` | `/api/v1/markets` | Public | Query: `category`, `sort`, `q`. **Valid sorts:** `volume`, `traders`, `newest`, **`active`**. Categories include `sports`, `politics`, `crypto`, `culture`, `economics`, `all`, plus legacy labels. Cached ~3s. |
| `GET` | `/api/v1/search` | Public | Unified local search (Polymarket + Kalshi + seed catalog in DB). `limit` 1–100. |
| `GET` | `/api/v1/markets/{slug}` | Public | Single market. |
| `GET` | `/api/v1/markets/{slug}/detail` | Public | Rich detail. |
| `GET` | `/api/v1/markets/{slug}/snapshot` | Public | Snapshot + L2 book activity. |
| `GET` | `/api/v1/markets/{slug}/book` | Public | Order book. |
| `GET` | `/api/v1/markets/{slug}/candles` | Public | OHLCV-style candles. |
| `GET` | `/api/v1/markets/{slug}/prices/latest` | Public | Latest price. |
| `GET` | `/api/v1/markets/{slug}/history` | Public | Price history. |
| `GET` | `/api/v1/markets/{slug}/prediction` | Public | Model prediction for slug. |
| `GET` | `/api/v1/markets/{slug}/explain` | Public | Explainer. |
| `GET` | `/api/v1/markets/{slug}/drivers` | Public | Drivers. |
| `GET` | `/api/v1/markets/{slug}/edge-history` | Public | Edge history. |
| `GET` | `/api/v1/markets/{slug}/agent-trace` | Public | Agent trace for market. |
| `GET` | `/api/v1/markets/{slug}/share-snapshot` | Public | Shareable snapshot payload. |
| `GET` | `/api/v1/markets/{slug}/latency` | Public | Analyst latency metrics. |
| `GET` | `/api/v1/home` | Public | Home rails payload. |
| `GET` | `/api/v1/feed` | Public | Unified feed page. |
| `GET` | `/api/v1/desk` | Public | Desk view. |
| `GET` | `/api/v1/opportunities` | Public | Opportunities list. |
| `GET` | `/api/v1/compare` | Public | Compare markets. |
| `GET` | `/api/v1/categories/{category}/summary` | Public | Category summary. |
| `GET` | `/api/v1/resolved` | Public | Resolved market review. |
| `GET` | `/api/v1/wc2026/schedule` | Public | WC2026 schedule. |

Canonical seeded test market: `nba-2025-01-15-lal-bos` (Lakers vs Celtics).

---

## Human paper trading (JWT)

Requires authenticated user. Enforces `PAPER_TRADING_ONLY=true`, open/unlocked market, optional off-market price guard (±0.10 vs latest non-seed snapshot).

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `POST` | `/api/v1/orders` | JWT | Open paper buy. Body: `slug`, `side` (`buy` or legacy `YES`/`NO`), `outcome` (`yes`/`no`), `shares` > 0, `price` in [0.01, 0.99]. Header **`Idempotency-Key`** optional — replay returns original order without double-debit. Response includes `paper_trading_only: true`. |
| `GET` | `/api/v1/orders/history` | JWT | Last 50 paper orders for user. |
| `POST` | `/api/v1/positions/close` | JWT | Close (sell) open paper position. Also accepts **`Idempotency-Key`**. |

### CLOB / agent paper path (separate ledger)

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `GET` | `/api/v1/paper-account` | Token / shared | Paper account bootstrap. |
| `GET` | `/api/v1/orders` | Paper token | CLOB order history (paginated; query `account_id`, optional `status`, `market`, `cursor`, `limit`). |
| `POST` | `/api/v1/markets/{slug}/orders` | Paper token | Place CLOB order after **`RiskService.validate(OrderIntent)`**. **`Idempotency-Key`** replays existing order. |
| `POST` | `/api/v1/orders/{order_id}/cancel` | Paper token | Cancel open CLOB order. Body includes `account_id`. Failures: `403` ownership, `409` state conflict, `404` missing. |
| `GET` | `/api/v1/accounts/{account_id}/positions` | Paper token | CLOB positions for account. |
| `GET` / `POST` | `/api/v1/markets/{slug}/signals` | Public / write rules in code | Paper signal summary / submit. |

**Cancel semantics (CLOB only):** cancel is ownership-checked and state-checked; partially filled / terminal orders raise conflict or not-found rather than silently succeeding. The human JWT path has **no cancel endpoint** — close with `POST /api/v1/positions/close` instead.

---

## Portfolio suite (JWT)

All require `get_current_user`. Transient DB failures return **503** (not empty success).

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/v1/portfolio` | Full portfolio positions + balances. |
| `GET` | `/api/v1/portfolio/summary` | Compact summary. |
| `GET` | `/api/v1/portfolio/risk` | Risk metrics (drawdown, open exposure, closed trades). |
| `GET` | `/api/v1/portfolio/attribution` | Trade attribution breakdown. |
| `GET` | `/api/v1/portfolio/equity-curve` | Equity curve points (`PortfolioEquitySnapshot`). |
| `GET` | `/api/v1/portfolio/exposure` | Grouped exposure. |
| `GET` | `/api/v1/portfolio/clv-summary` | Closing-line value summary for paper book. |
| `GET` | `/api/v1/profile` | Trader profile surface. |

---

## Leaderboard

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `GET` | `/api/v1/leaderboard` | Public | Ranked paper traders. Query: `limit`, `offset`, `sort` (default `realized_pnl`). Anonymized usernames; ROI / win_rate / realized_pnl. TTL cache. |

---

## Activity, alerts, watchlist

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `GET` | `/api/v1/activity/trades` | Public | Anonymized public paper trades (cursor page). Always `paper_trading_only: true`. |
| `GET` | `/api/v1/alerts` | Public | Alert rows (`limit`/`offset`/`alert_type`). |
| `GET` | `/api/v1/alerts/feed` | Public | Structured alert feed. |
| `GET` | `/api/v1/alerts/digest` | Public | Digest. |
| `GET` | `/api/v1/watchlist/alerts` | Public | Watchlist-scoped alerts. |
| `GET` | `/api/v1/watchlist` | JWT | List watchlist. |
| `POST` | `/api/v1/watchlist` | JWT | Add slug. |
| `DELETE` | `/api/v1/watchlist/{slug}` | JWT | Remove slug. |
| `GET` / `PUT` | `/api/v1/notify/prefs` | JWT | Notification preferences. |

---

## Signals & analyst

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `GET` | `/api/v1/signals` | Public | Signal feed (alias of feed). |
| `GET` | `/api/v1/signals/feed` | Public | Signal feed. |
| `GET` | `/api/v1/signals/events` | Public | Raw signal events (`market`, `signal_type`, optional dedupe window). |
| `GET` | `/api/v1/signals/dashboard` | Public | Signals dashboard. |
| `GET` | `/api/v1/signals/arbitrage` | Public | Arb signal. |
| `GET` | `/api/v1/signals/dutching` | Public | Dutching. |
| `GET` | `/api/v1/signals/screeners` | Public | Screeners. |
| `GET` | `/api/v1/signals/smart-money` | Public | Smart-money signal. |
| `GET` | `/api/v1/signals/forecast` | Public | Forecast signal. |
| `GET` | `/api/v1/smart-money` | Public | Smart-money panel. |
| `GET` | `/api/v1/clv-track-record` | Public | CLV track record. |
| `GET` | `/api/v1/track-record` | Public | Forecast track record. |
| `GET` | `/api/v1/briefs` | Public | Analyst briefs list. |
| `GET` | `/api/v1/briefs/{brief_id}` | Public | Single brief. |
| `POST` | `/api/v1/analyst/run` | (see code) | On-demand analyst run. |
| `GET` | `/api/v1/analyst/track-record` | Public | Analyst track record. |
| `GET` | `/api/v1/analyst/track-record/claims` | Public | Claims list. |
| `GET` | `/api/v1/arb/opportunities` | Public | Arb opportunities. |
| `POST` | `/api/v1/arb/detect` | Public | Trigger detect. |
| `GET` | `/api/v1/memories` | Public | Memory list. |
| `GET` | `/api/v1/macro` | Public | Macro dashboard. |
| `GET` | `/api/v1/weather/edges` | Public | Weather edges. |
| `GET` | `/api/v1/sports/results` | Public | ESPN NBA results signals (read-only; does not settle markets). |
| `POST` | `/api/v1/sports/ingest` | **Admin** | Persist final-game sports signal events only (no market resolution). |

---

## Evaluation, calibration, drift

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `GET` | `/api/v1/eval/evaluations` | Public | Recent evaluations (Brier, predicted_prob, actual_outcome). |
| `GET` | `/api/v1/eval/aggregates` | Public | Mean Brier, calibration error, market count. |
| `GET` | `/api/v1/eval/calibration` | Public | Calibration bins. |
| `GET` | `/api/v1/calibration/latest` | Public | Latest calibration payload. |
| `GET` | `/api/v1/admin/observability/drift` | **Admin** | Calibration drift vs baseline; may fire alert only if `DRIFT_ALARM_ENABLED=true`. |
| `GET` | `/api/v1/admin/observability/traces` | **Admin** | Agent run traces. |
| `GET` | `/api/v1/admin/observability/slo` | **Admin** | Latency SLO tiles. |
| `GET` | `/api/v1/admin/observability/summary` | **Admin** | Combined observability. |

There is **no** public `GET /api/v1/eval/drift`. Drift lives under **admin observability**.

---

## WebSocket

WebSocket routes are implemented in `backend/app/api/v1/ws.py` (not always present in the OpenAPI JSON snapshot). Both require `PAPER_TRADING_ONLY=true` or the socket closes with policy violation.

### `WS /api/v1/ws/prices?market={slug}`

- Validates slug against catalog or DB.
- Sends initial `{slug, yes, no, ts}` then hub ticks for that market slug.
- ~29s idle keeps connection without payload spam.

### `WS /api/v1/ws/feed`

Multiplexed channels. On connect: `{channel: "system", connected: true, ts}`. Keepalive: `{channel: "system", keepalive: true}`.

| Channel / topic | Source | Meaning |
|-----------------|--------|---------|
| `system` | socket | Connect + keepalive frames. |
| `briefs` | hub | Analyst brief updates. |
| `alerts` | hub | Dispatched alerts. |
| `feed` | hub | Unified feed events. |
| `activity` | hub | Public paper-trade activity. |
| `market.tick` | in-process bus | Market tick. |
| `signal.new` | bus | New signal. |
| `order.filled` | bus | Order fill. |
| `order.cancelled` | bus | Order cancel. |
| `market.resolved` | bus | Market resolution. |

Frames are shaped as `{channel: <topic>, ...payload}`.

---

## Admin (gated)

All require `X-Admin-API-Key` unless noted.

### Legacy `/admin/*` (prefix without `/api/v1`)

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/admin/markets` | Create market. |
| `POST` | `/admin/markets/{market_id}/lock` | Lock market. |
| `POST` | `/admin/markets/{market_id}/resolve` | Resolve market. |
| `GET` | `/admin/smoke-account` | Smoke paper account. |
| `GET`/`POST` | `/admin/historical-closing-snapshot-captures` | Closing snapshot capture. |
| `GET` | `/admin/market-snapshot-captures` | List captures. |
| `GET`/`POST` | `/admin/phase3-snapshot-store-backtests` | Phase3 snapshot-store backtest. |
| `GET` | `/admin/agents/runs` | List agent runs. |
| `GET` | `/admin/agents/runs/{run_id}` | Get run. |
| `POST` | `/admin/agents/run/{slug}` | Run agent on market. |

### `/api/v1/admin/*`

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/v1/admin/markets` | Admin market list. |
| `GET` | `/api/v1/admin/jobs` | Job runs. |
| `POST` | `/api/v1/admin/markets/{slug}/resolve` | Resolve + settle paper orders. |
| `POST` | `/api/v1/admin/wc2026/seed` | Seed WC2026. |
| `POST` | `/api/v1/admin/wc2026/resolve` | Resolve WC2026. |
| `GET` | `/api/v1/admin/wc2026/status` | WC2026 status. |
| Observability suite | see Evaluation section | traces / drift / slo / summary. |
| Forecast-mirror admin | `/api/v1/admin/dogfood/mirror-report`, external resolve | Mirror ops. |

---

## Other public / product surfaces (verified in OpenAPI)

| Area | Paths |
|------|-------|
| Backtest | `POST/GET /api/v1/backtest/run`, `GET .../runs`, `.../runs/{run_id}`, `.../summary` |
| Clones | CRUD under `/api/v1/clones`, leaderboard, nodes, scorecard, run |
| Assistant | `POST /api/v1/assistant/chat` |
| Forecast mirror | forecasters anonymous/recover, forecasts create, dashboard, lifecycle, telemetry, backfill |
| Calibration | `GET /api/v1/calibration/latest` |

---

## Error shapes (common)

| Status | Typical meaning |
|--------|-----------------|
| `400` | Validation / insufficient balance / risk failure / bad category. |
| `401` | Missing/invalid JWT, paper token, or metrics auth. |
| `403` | CLOB cancel ownership failure. |
| `404` | Market or order not found. |
| `409` | Market resolved/locked; price too far from market; CLOB state conflict; signup email taken. |
| `422` | Schema validation. |
| `429` | Rate limited. |
| `500` | Generic internal error body (`detail: Internal Server Error`); request id header when available. |
| `503` | `PAPER_TRADING_ONLY` false on trading path; portfolio temporarily unavailable. |

---

## Source of truth

| Artifact | Role |
|----------|------|
| `backend/app/main.py` | Router mount list. |
| `backend/app/api/v1/**` | Route implementations. |
| `backend/app/admin/**` | Admin market/agent routes. |
| `backend/tests/fixtures/openapi_snapshot.json` | Frozen path/method catalog (HTTP). |
| Live `GET /openapi.json` | Runtime schema when server is up. |

**Not documented as features here:** cash deposits, withdrawal rails, real-money execution, auto-activation of alternate ML models on A/B win, or any endpoint absent from the snapshot/code.
