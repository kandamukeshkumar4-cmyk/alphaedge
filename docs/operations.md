# AlphaEdge operations runbook

> **Paper-trading only.** Production and local stacks must set
> `PAPER_TRADING_ONLY=true`. Settings validation **rejects** boot when the flag
> is false (`backend/app/core/config.py`). Never put secret values, connection
> strings with passwords, or tokens into this document or commits.

This runbook is for operators deploying and monitoring AlphaEdge. Product
behavior for end users is in [user-guide.md](./user-guide.md); HTTP surface is
in [api.md](./api.md).

---

## 1. Current production topology (as coded)

| Layer | Role | Notes |
|-------|------|--------|
| Backend API | FastAPI + in-process schedulers | Dockerfile under `backend/` |
| Frontend | Next.js on Vercel | `frontend/`; `NEXT_PUBLIC_API_URL` points at API |
| Database | Postgres (historically Neon; Railway Postgres also used) | `DATABASE_URL` (async) + `DATABASE_URL_SYNC` |
| Redis | Optional ARQ worker queue | Free-tier often uses `REDIS_URL=redis://disabled…` so schedulers run **in-process** inside the API |
| Worker | Optional separate process | `backend/railway.worker.toml` → `python -m app.workers.main` |

**Uptime monitor defaults** (`.github/workflows/demo-uptime.yml` env):

| Variable in workflow | Purpose |
|----------------------|---------|
| `BASE_URL` | Backend base used by wake + `verify_prod.py` |
| `FRONTEND_URL` | Frontend base used by `verify_prod.py` |

Those URLs are **production hosts**, not credentials. Rotate secrets only in
Railway / Vercel / GitHub Actions secret stores — never paste them here.

Canonical public frontend name used across docs and CI:
`alphaedge-frontend-three.vercel.app`. The former Azure Static Web Apps host is
**retired (404)** and must not be used for CORS, uptime, or user links.

---

## 2. Deploy path — Railway API

### Preferred: scripted deploy from repo root

`scripts/deploy_railway.ps1` (requires Railway CLI + project token):

1. Asserts `RAILWAY_TOKEN`, `NEON_DATABASE_URL` (or Postgres URL), `ADMIN_API_KEY`,
   `JWT_SECRET_KEY`.
2. Sets service variables on Railway service **`alphaedge-api`** (names only —
   script prints that secrets will not be echoed).
3. `Push-Location backend` then:

   ```text
   railway up --service alphaedge-api --detach
   ```

4. Optionally points frontend at the new API via
   `scripts/set_frontend_api_url.ps1`.

Variables the script sets (values never documented here):

| Name | Purpose |
|------|---------|
| `PORT` | Listen port hint (script uses `8000`; Railway also injects `$PORT`) |
| `PAPER_TRADING_ONLY` | Must be `true` |
| `APP_ENV` | `production` (enables secret validators + secure cookies + shared-account lockdown) |
| `DATABASE_URL` | Async SQLAlchemy URL (`postgresql+asyncpg://…`) |
| `DATABASE_URL_SYNC` | Sync URL for Alembic / workers |
| `ADMIN_API_KEY` | Admin + metrics gate |
| `JWT_SECRET_KEY` | JWT signing (required non-default in prod) |
| `CORS_ORIGINS` | Allowed browser origins |
| `REDIS_URL` | Queue; disabled sentinel runs schedulers in-process |

### Build gotcha: context must be `backend/`

From `goals/build-loop-e2e/STATE.md` (loop deploy lessons):

- Running `railway up` from the **wrong directory** can upload the **repo root**
  and fail Railpack auto-detect.
- Fix used in that loop:

  ```text
  railway up ./backend --path-as-root --service alphaedge-api
  ```

  so the Docker context is `backend/` (where `Dockerfile` + `railway.toml` live).

`deploy_railway.ps1` achieves the same by `Push-Location $BackendDir` before
`railway up`.

### `backend/railway.toml` (verified)

| Key | Behavior |
|-----|----------|
| builder | DOCKERFILE |
| dockerfilePath | Dockerfile |
| preDeployCommand | `uv run alembic upgrade head` — migrations **before** traffic |
| startCommand | `sh -c 'uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}'` |
| healthcheckPath | `/health` |
| healthcheckTimeout | 120 |
| restartPolicyType | ON_FAILURE |

Why pre-deploy migrations: cold-schema Alembic during the start command can
starve the healthcheck window (documented in `railway.toml` comments).

### Optional worker service

`backend/railway.worker.toml`:

```text
startCommand = "python -m app.workers.main"
```

Use when Redis/ARQ is enabled; on the workerless free tier, in-process
schedulers cover news/weather/research/whale/resolve loops instead.

### Frontend (Vercel)

```text
cd frontend
npx vercel --prod --yes
```

Env: `NEXT_PUBLIC_API_URL` = public API origin (HTTPS, no trailing slash).

---

## 3. Environment variables (names + purpose only)

### Required / strongly expected in production

| Name | Purpose |
|------|---------|
| `PAPER_TRADING_ONLY` | Must be `true` — boot fails if false |
| `APP_ENV` | `production` / `staging` / `development` — prod forbids default secrets |
| `DATABASE_URL` | Async Postgres DSN |
| `DATABASE_URL_SYNC` | Sync Postgres DSN (Alembic) |
| `ADMIN_API_KEY` | Admin routes + Prometheus `/metrics` (unless metrics token set) |
| `JWT_SECRET_KEY` | User session JWT secret |
| `CORS_ORIGINS` | Comma-separated browser origins |
| `REDIS_URL` | Redis; use disabled sentinel to skip external Redis |

### Ops / observability

| Name | Purpose |
|------|---------|
| `METRICS_TOKEN` | Optional Bearer for Prometheus scrape (empty → admin key only) |
| `RATE_LIMIT` | Global SlowAPI limit |
| `RATE_LIMIT_MUTATING` / `RATE_LIMIT_MUTATING_ENABLED` | Stricter mutating limit |
| `OPS_ALERT_ERROR_RATE_THRESHOLD` | In-app ops alert threshold |
| `OPS_ALERT_MIN_REQUESTS` | Min sample before error-rate alert |
| `OPS_ALERT_P99_MS` | Latency alert threshold |
| `OPS_ALERT_STALE_PREDICTION_HOURS` | Stale prediction alert |

### Schedulers & streams (defaults mostly on)

| Name | Purpose |
|------|---------|
| `SCHEDULER_NEWS_SCAN_ENABLED` | In-process news scan loop |
| `SCHEDULER_WEATHER_SCAN_ENABLED` | Weather scan |
| `SCHEDULER_MORNING_RESEARCH_ENABLED` | Morning research |
| `SCHEDULER_WHALE_REFRESH_ENABLED` | Whale refresh (legacy research loop) |
| `SCHEDULER_WHALE_FLOW_ENABLED` / `WHALE_FLOW_ENABLED` | Large-trade whale flow loop (Wave 10 / V58 — `4f9cb97`) |
| `SCHEDULER_VENUE_GAP_ENABLED` / `VENUE_GAP_ENABLED` | Cross-venue gap loop (Wave 10 / V58 — `4f9cb97`) |
| `HEARTBEAT_MANAGER_ENABLED` | Code-only position heartbeat (Wave 10 / V59 — land `09af5eb`; default **false** in code) |
| `PODS_ENABLED` | Multi-pod paper engine runner (Wave 10 / V57 — `40aeeec`; default **false** in code) |
| `SCHEDULER_WC2026_RESOLVE_ENABLED` | WC2026 resolve |
| `SCHEDULER_EXTERNAL_RESOLVE_ENABLED` | Venue resolve + score locked forecasts |
| `SCHEDULER_EXTERNAL_AUTOLOCK_ENABLED` | Auto-lock pre-close model forecasts |
| `KALSHI_WS_ENABLED` / `POLYMARKET_WS_ENABLED` | Venue price WebSockets |
| `LIVE_FEED_ENABLED` / `LIVE_TICK_*` | Live tick pacing / idle scale-to-zero friendly intervals |

### ML / drift / ensemble

| Name | Purpose |
|------|---------|
| `ML_MODEL_TYPE` | Deployed default (`xgboost` or `lightgbm`) — **not** auto-flipped by A/B |
| `AB_MODEL_TYPE_HISTORY_VERIFIED` / `AB_MODEL_TYPE_HISTORY_EVIDENCE` | Non-secret operator reference to Railway deploy/config history; A/B refuses when absent |
| `ENSEMBLE_ENABLED` | Multi-model ensemble router |
| `DRIFT_ALARM_ENABLED` | When true, drift endpoint may fire T09 alerts |
| `DRIFT_ALARM_THRESHOLD` | Absolute Brier drift threshold |
| `DRIFT_ROLLING_WINDOW` | Rolling graded sample size for drift |
| `BACKTEST_NIGHTLY_ENABLED` / `BACKTEST_NIGHTLY_SLUGS` | Optional nightly backtest job |

### Optional external keys (feature-dependent)

| Name | Purpose |
|------|---------|
| `LLM_API_KEY` / `NIM_API_KEY` / provider keys | LLM analyst / assistant |
| `GEMINI_API_KEY` | Gemini judge/reasoning fallback path |
| `LANGSMITH_API_KEY` | Tracing |
| `ODDS_API_KEY` | Live odds |
| `FRED_API_KEY` | Macro desk |
| `KALSHI_API_KEY_ID` / `KALSHI_SIGNING_PEM` | Authenticated Kalshi |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` / `ALERTS_WEBHOOK_URL` | External alert delivery (off by default) |

Full field list: `backend/app/core/config.py`. Local template (no secrets):
`.env.example`.

---

## 4. Migrations policy

| Rule | Detail |
|------|--------|
| Tool | Alembic under `backend/alembic/` |
| Pre-deploy | Railway `preDeployCommand`: `uv run alembic upgrade head` |
| Local/docker | `docker-compose` / Dockerfile start: `alembic upgrade head` then uvicorn |
| **Single head** | Graph must remain **one head**. Dual `017_*` revisions are **merged** by `018_wc2026_tag` (`down_revision = ("017_user_onboarding", "017_position_settled")`). Current tip is `040_portfolio_equity_snapshots` → `039_order_expiry`. |
| New migrations | Always set `down_revision` to the **current single head**; never open a second unmerged branch for prod |
| Prod-critical note | `alembic upgrade head` fails on multi-head graphs — deploy will not pass pre-deploy |

**Operator checklist before merge to deploy branch:**

```text
cd backend
uv run alembic heads    # expect exactly one head
uv run alembic upgrade head
```

---

## 5. Monitoring

### A. Demo uptime cron (GitHub Actions)

File: `.github/workflows/demo-uptime.yml`

| Item | Behavior |
|------|----------|
| Schedule | `*/15 * * * *` (15-minute cron) |
| Wake | Curl `{BASE_URL}/health` up to ~5 minutes for cold start |
| Assert | `status == ok` and **`paper_trading_only is True`** |
| Verify | `python3 scripts/verify_prod.py --api $BASE_URL --frontend $FRONTEND_URL` (checks 1–6) |
| Journey | Full signup+paper order **not** on cron by default in the schedule path; optional via `workflow_dispatch` `run_full_journey` (avoid junk orders every 15 minutes) |

`scripts/verify_prod.py` checks (stdlib only): health, markets richness,
candles, signals, frontend homepage content, memories endpoint.

### B. Gated Prometheus metrics

| Endpoint | Auth | Format |
|----------|------|--------|
| `GET /metrics` | `X-Admin-API-Key` **or** `Authorization: Bearer <METRICS_TOKEN>` | Prometheus text |

Unauthorized → `401`. Implementation: `backend/app/observability/metrics.py`.

### C. Public system heartbeats (no secrets)

| Endpoint | Use |
|----------|-----|
| `GET /api/v1/system/loops` | Planned vs running background loops + last heartbeat (`never` if never beat) |
| `GET /api/v1/system/metrics` | In-process HTTP/cache counters (not Prometheus) |
| `GET /api/v1/system/resolved-count` | Forecast-score nominal population plus correlation-cluster A/B readiness; does not flip model |
| `GET /api/v1/system/model-ab` | Cached controlled comparison only; public GET never trains; `applied` always false |
| `GET /api/v1/system/sources` | **Admin** connector health registry |
| `GET /api/v1/admin/observability/*` | **Admin** traces / drift / SLO / summary |
| `GET /health` | Liveness |

Refresh the cache through an operator-controlled Railway shell/job, never via
the public GET:

```bash
AB_MODEL_TYPE_HISTORY_VERIFIED=true \
AB_MODEL_TYPE_HISTORY_EVIDENCE='Railway deployment/config-history reference' \
uv run python scripts/refresh_model_ab.py
```

The evidence value is a non-secret reference for the operator handoff. Without
both settings the script persists an honest `model_type_history_unverified`
refusal and no Brier comparison.

### D. After deploy smoke

```text
py -3.13 scripts/verify_prod.py --api https://<api-host> --frontend https://alphaedge-frontend-three.vercel.app
```

Orchestration rule: deploy-affecting work is not done until this (or the
project’s `verify_prod` equivalent) passes against **production**, not localhost.

---

## 6. Neon → Railway migration story (+ rollback note)

### Why the cutover happened

Historical free-tier backend ran on **Hugging Face Docker Space + Neon
Postgres**. Operational pain (from loop notes + deploy docs):

- HF Space **sleep** after inactivity (cold starts).
- Neon **suspend** / egress quota exhaustion can make `alembic upgrade head` fail
  at boot (backend down until DB accepts connections).
- Goal of Railway path: single API service with Dockerfile build, pre-deploy
  migrations, and a stable public `*.up.railway.app` host monitored by
  `demo-uptime.yml`.

### Forward migration pattern (logical steps)

1. **Provision** Railway service `alphaedge-api` with Root / path context =
   `backend/` (`railway up ./backend --path-as-root` or script `cd backend`).
2. **Point DB vars** at Postgres:
   - Either continue using **Neon** URLs (`NEON_DATABASE_URL` →
     `DATABASE_URL` / `_SYNC`), or
   - Attach **Railway Postgres** and use private/public DATABASE_URL templates.
3. **Set production secrets** (`ADMIN_API_KEY`, `JWT_SECRET_KEY`,
   `PAPER_TRADING_ONLY=true`, `APP_ENV=production`, `CORS_ORIGINS` including the
   Vercel origin).
4. **Deploy** (`preDeployCommand` runs Alembic to **head**).
5. **Repoint frontend** `NEXT_PUBLIC_API_URL` (and CORS) to the Railway public
   domain.
6. **Update monitors** — `demo-uptime.yml` `BASE_URL` already targets the Railway
   production host in-tree; keep it aligned when the domain changes.
7. **Retire or leave idle** the HF Space so it is not dual-writing confusion;
   do not delete DB until cutover is proven.

### Rollback copy note

If Railway API is unhealthy but **the same Postgres** still holds data:

| Scenario | Rollback action |
|----------|-----------------|
| Bad API image only | Redeploy previous Railway deployment / image; DB stays put |
| Wrong env / CORS | Fix service variables; no data migration |
| Need prior host (e.g. HF) temporarily | Point `NEXT_PUBLIC_API_URL` + CORS + uptime `BASE_URL` back to the previous API host **if that host still has the same `DATABASE_URL`** |
| DB was **copied** to a new cluster | Rolling back API alone is not enough — restore DNS/env to the **database that still has the latest ledger**, or restore a Postgres backup taken **before** cutover |
| Neon egress restored | Can reattach Neon DSNs to either host; avoid two APIs writing the same DB concurrently |

**Copy rule of thumb:** treat `DATABASE_URL` ownership as single-writer. Prefer
moving the **API process** between hosts over forking the database. If you must
clone Postgres for a hard cut, take a consistent snapshot, upgrade Alembic once
on the target, then switch API + frontend + uptime together. Keep the previous
API scaled to zero (not dual-active) until verification passes.

---

## 7. Local operations quick commands

```text
# API + db + redis
docker compose up --build

# Full stack with worker profile
docker compose --profile full up --build

# Backend tests
cd backend
uv run --extra dev pytest -q
uv run --extra dev ruff check app tests

# Frontend
cd frontend
npm install
npm run lint
npm run typecheck
npm run build
npm run test:e2e   # Playwright suite when configured
```

---

## 8. Incident cheat sheet

| Symptom | First checks |
|---------|----------------|
| Uptime workflow red | Curl `/health`; confirm `paper_trading_only`; cold-start wait; Neon/Railway DB awake |
| 5xx on public GETs | `GET /api/v1/system/loops` + admin observability; connector sources |
| Empty markets UI | `verify_prod` markets check; live ingest loops planned/running |
| Autolock funnel starved | See §10 — bridge → autolock → external_resolve → scores |
| Migration deploy fail | `alembic heads` multi-head? pre-deploy logs |
| Metrics scrape 401 | Admin key or `METRICS_TOKEN` |
| JWT/admin boot fail in prod | Default secrets rejected when `APP_ENV` is production/staging |

---

## 9. Background loops (`GET /api/v1/system/loops`)

Canonical name list is `_ALL_LOOPS` in `backend/app/api/v1/system.py`. The
endpoint returns `planned` (settings / data-stream plan), heartbeat `status`
(`never` if never beat), and `detail`. **No secrets.** Heartbeats are recorded
from in-process lifespan loops in `backend/app/main.py` and/or ARQ crons in
`backend/app/workers/tasks.py` (free tier often has **no** separate worker —
schedulers run inside the API process).

### Full catalog (must match `_ALL_LOOPS`)

| Loop name | Role (ops) | Primary code |
|-----------|------------|--------------|
| `price_feed` | Seed/catalog price ticks | `main.py` price-feed loop |
| `live_ingest` | Venue catalog ingest | live ingest loop |
| `live_tick` | Live tick pacing | live tick loop |
| `eval` | Evaluation scoring pass | eval loop |
| `kalshi_ws` / `polymarket_ws` | Venue WebSocket streams | data streams plan |
| `news_scan` / `weather_scan` / `morning_research` / `whale_refresh` | Research schedulers | flag-gated in-process loops |
| **`whale_flow`** | Large-trade tape → whale pressure (Wave 10 / V58 — `4f9cb97`) | `services/whale_flow_service.py` + `main.py` / ARQ task |
| **`venue_gap`** | Cross-venue implied gap store (Wave 10 / V58 — `4f9cb97`) | `services/venue_gap_service.py` + `main.py` / ARQ task |
| `wc2026_resolve` | WC2026 resolution helper | scheduler |
| `external_resolve` | Venue resolve + grade locked forecasts | external resolve loop |
| **`external_market_bridge`** | Register **ingested** venue markets as `ExternalMarket` rows so autolock has input | `workers/external_market_bridge.py` |
| **`forecast_autolock`** | Bounded pre-close **model** LIVE forecast locks (no orders, no resolve) | `workers/forecast_autolock.py` |
| `drift_detect` | Persist ForecastScore drift snapshots (feeds public `/eval/drift`) | drift worker |
| **`ops_alerts`** | Threshold evaluator → in-app `Alert` rows (error rate, p99, stale predictions) | `workers/ops_alerts.py` |
| `portfolio_equity` | Equity snapshot writer for portfolio curves | equity scheduler |
| **`daily_digest`** | Per-user daily **in-app** Notification digest (no email) | `workers/daily_digest.py` |
| **`jobrun_retention`** | Delete old `job_runs` (default 30d, flag-gated) | `workers/jobrun_retention.py` |
| **`data_retention`** | Odds downsample + signal/notification prune (flag-gated) | `workers/data_retention.py` |
| **`heartbeat_manager`** | Code-only position heartbeat (hold/tighten/exit/emergency); decision log (Wave 10 / V59 land `09af5eb`) | `services/heartbeat_manager.py` |
| **`pod_runner`** | Multi-pod paper strategy scan/score/enter/exit (Wave 10 / V57 — `40aeeec`) | `pods/runner.py` |

Verify names in a running API:

```text
# Public
curl -sS "$BASE_URL/api/v1/system/loops" | python -c "import sys,json; d=json.load(sys.stdin); print([x['name'] for x in d['loops']])"
# Expect exactly the _ALL_LOOPS order/names above.
```

### Newer loops operators care about (waves 4–8)

| Loop | What “healthy” looks like | Failure modes |
|------|---------------------------|---------------|
| `external_market_bridge` | Heartbeat `ok`; JobRun summaries show bridged > 0 when open venue markets exist | Bridging **seed** markets is forbidden; wrong identity key starves resolver |
| `forecast_autolock` | Locks only OPEN external markets with future `close_at` in window; `SCHEDULER_EXTERNAL_AUTOLOCK_ENABLED` | Zero candidates when bridge never ran or all already have LIVE forecasts |
| `daily_digest` | One digest Notification per user/day (`type=digest`) | Missing equity snapshots → thinner copy; still in-app only |
| `ops_alerts` | Alerts via existing `AlertDispatchService` / WS `alerts` channel | Needs min request volume before error-rate fires; empty PredictionLog does **not** raise stale alert |
| `jobrun_retention` / `data_retention` | `deleted=0` on second pass (idempotent) | Never touches order path; unread notifications kept forever by data retention |

Related env flags (names only): `SCHEDULER_EXTERNAL_AUTOLOCK_ENABLED`,
`SCHEDULER_OPS_ALERTS_ENABLED`, `SCHEDULER_DAILY_DIGEST_ENABLED`,
`JOBRUN_RETENTION_ENABLED` / `JOBRUN_RETENTION_DAYS`,
`DATA_RETENTION_ENABLED`, odds/signal/notification retention day settings in
`backend/app/core/config.py`.

### Wave 10 loops (V57–V59 / V58 pipeline)

Ship SHAs: V58 `4f9cb97`, V59 land `09af5eb` + chain `91239e3`, V57
`40aeeec`. Full narrative: [docs/releases/wave-10.md](./releases/wave-10.md).

| Loop | What “healthy” looks like | Failure modes / flags |
|------|---------------------------|------------------------|
| **`whale_flow`** | Heartbeat `ok`; detail like `fetched=… inserted=…`; pressure updates for large CASH tape trades | Off when `WHALE_FLOW_ENABLED` / `SCHEDULER_WHALE_FLOW_ENABLED` false; circuit breaker + min poll; external data-api only (read-only) |
| **`venue_gap`** | Heartbeat `ok`; detail like `upserted=… skipped_odds=…`; `GET /api/v1/venue-gaps` non-error | Off when `VENUE_GAP_ENABLED` / `SCHEDULER_VENUE_GAP_ENABLED` false; stale pairs when odds missing |
| **`heartbeat_manager`** | Heartbeat `ok`; detail counts `scanned` / `hold` / `exit` / `emergency`; `GET /api/v1/heartbeat/decisions` grows | Code default **off** (`HEARTBEAT_MANAGER_ENABLED=false`); enable in Railway to run; JWT `*_logged` ≠ filled CLOB exit |
| **`pod_runner`** | Heartbeat `ok`; detail `scanned` / `scored` / `entered` / `exited`; `GET /api/v1/pods` shows pod keys | Code default **off** (`PODS_ENABLED=false`); skip reason `PODS_ENABLED=false` when disabled; never bypasses RiskService order path |

```text
# Spot-check the four Wave 10 loops on a live API (no secrets)
curl -sS "$BASE_URL/api/v1/system/loops" | python -c "import sys,json; d=json.load(sys.stdin); want={'whale_flow','venue_gap','heartbeat_manager','pod_runner'};
print([x for x in d['loops'] if x['name'] in want])"
curl -sS "$BASE_URL/api/v1/pods"
curl -sS "$BASE_URL/api/v1/heartbeat/decisions?limit=10"
```

**Note on `planned` vs `running`:** `GET /api/v1/system/loops` may show
`planned: false` while `running: true` if the loop is started from lifespan
tasks / env outside the older `background_loop_plan` list. Trust heartbeats +
detail strings for liveness; fix plan drift in a code loop if you need them to
match.

---

## 9b. Heartbeat position manager (Loop V59)

Code-only in-process loop (default **off**: `HEARTBEAT_MANAGER_ENABLED=false`).
Cadence default **45s** (`HEARTBEAT_MANAGER_INTERVAL_SEC`). No LLM calls.

**Land SHAs (no titled `merge(loop59)` in `git log --merges -15`):**
`91239e3` (migration re-chain), `09af5eb` (config union with V58), feature
tickets `8c4c293`…`ce099e9`. See [wave-10.md](./releases/wave-10.md).

| Concern | How |
|---------|-----|
| Liveness + detail counts | `GET /api/v1/system/loops` → `heartbeat_manager` (`scanned=… hold=… exit=…`) |
| Decision audit log | `GET /api/v1/heartbeat/decisions?limit=50` (public read) |
| Order path | CLOB exits only via `RiskService` → `OrderIntent(is_exit=True)` → `OrderBookService` |
| Emergency halts | `HEARTBEAT_GLOBAL_KILL`; price-feed staleness; daily-loss (pod ledger read-only when V57 registry present) — all logged, reversible when condition clears |

Rules (config): `HEARTBEAT_TIME_STOP_SEC`, `HEARTBEAT_ADVERSE_MOVE_PCT`,
`HEARTBEAT_PROFIT_TARGET_PCT`, `HEARTBEAT_STALENESS_SEC`,
`HEARTBEAT_TIGHTEN_ADVERSE_PCT`, `HEARTBEAT_DAILY_LOSS_HALT_PCT`.

```text
curl -sS "$BASE_URL/api/v1/heartbeat/decisions?limit=20"
curl -sS "$BASE_URL/api/v1/system/loops" | python -c "import sys,json; d=json.load(sys.stdin); print([x for x in d['loops'] if x['name']=='heartbeat_manager'][0])"
```

**Do not** treat JWT paper `exit_logged` / `emergency_logged` rows as filled
orders — those are auditable recommendations; CLOB exits show `*_submitted`
only after RiskService approval.

---

## 9c. Pod runner + paper pods (Loop V57)

In-process multi-pod paper engine (merge-resolve `40aeeec`). Default **off** in
code: `PODS_ENABLED=false`. Cadence ~60s (`pods/runner.py`).

| Concern | How |
|---------|-----|
| Liveness | `GET /api/v1/system/loops` → `pod_runner` detail `scanned=… scored=… entered=… exited=…` |
| Fleet status | `GET /api/v1/pods` — public read; `paper_trading_only` always true on response |
| UI | Frontend `/pods` (Wave 10 / V60 — `8ae25a4`); honest empty / not-deployed states |
| Order path | Pods **must not** bypass RiskService → OrderIntent → OrderBookService |

Three strategy keys from the engine design (`48933a3` / live pods payload):
`crypto_5m_momentum_fade`, `longshot_fade`, `sports_value`.

```text
curl -sS "$BASE_URL/api/v1/pods"
curl -sS "$BASE_URL/api/v1/system/loops" | python -c "import sys,json; d=json.load(sys.stdin); print([x for x in d['loops'] if x['name']=='pod_runner'][0])"
```

---

## 9d. Whale flow + venue gap (Loop V58)

Master data pipeline merge `4f9cb97`. Defaults in code: whale flow and venue
gap schedulers **on** (`WHALE_FLOW_ENABLED` / `VENUE_GAP_ENABLED` and their
`SCHEDULER_*` twins default true); graph injection of whale pressure remains a
separate flag (`WHALE_SIGNAL_ENABLED`, default false per V58 STATE).

| Loop | Cadence | Primary API / side effect |
|------|---------|---------------------------|
| `whale_flow` | ~60s | Large-trade tape → pressure; feeds context |
| `venue_gap` | ~60s | PM−KS gap store; `GET /api/v1/venue-gaps` |
| context | on read | `GET /api/v1/markets/{slug}/context`, `GET /api/v1/context/digest` |

```text
curl -sS "$BASE_URL/api/v1/venue-gaps"
curl -sS "$BASE_URL/api/v1/markets/<slug>/context"
curl -sS "$BASE_URL/api/v1/context/digest"
```

Leakage rule (from V58 STATE): observations timestamped at capture; consumers
filter pre-close only. No order-path changes in this pipeline.

---

## 10. Autolock funnel observability

The graded-forecast pipeline is a **funnel**. Each stage is a separate loop;
starvation at any stage yields thin track records and
`resolved-count.source = paper_orders_fallback`.

```text
live_ingest (markets catalog)
    → external_market_bridge  (ExternalMarket rows; open venue only)
    → forecast_autolock       (LIVE ForecastLog locks pre-close)
    → external_resolve        (venue outcome + ForecastScore)
    → eval / track-record / system/resolved-count (source=forecast_scores)
```

| Check | How |
|-------|-----|
| Loop heartbeats | `GET /api/v1/system/loops` — `external_market_bridge`, `forecast_autolock`, `external_resolve` |
| Population honesty | `GET /api/v1/system/resolved-count` → `source`, `forecast_scored_count` |
| Admin aggregates | `GET /api/v1/admin/stats` (forecasts locked/graded counts) — **admin key** |
| Drift series | `GET /api/v1/eval/drift` (public) after `drift_detect` has written rows |

**Do not** treat a rising `resolved_count` under `paper_orders_fallback` as proof
the forecast funnel is working — that count is the paper-order fallback
population (`ab_harness.resolved_outcomes_breakdown`).

Bridge invariants (from worker docstring): does **not** lock, score, resolve, or
write winning outcomes; keys venue identity via `external_slug` round-trip, not
catalog `external_id` alone.

---

## 11. Visual regression (local visreg)

Loop V44 — **local-only** Playwright visual baselines. CI must not require
ubuntu PNGs.

| Item | Location / command |
|------|--------------------|
| Spec | `frontend/e2e/visreg.spec.ts` |
| Masking / freeze helpers | `frontend/e2e/helpers/stable-shot.ts` |
| Project | Playwright project **`visreg`** in `frontend/playwright.config.ts` |
| Snapshots | `e2e/visreg.spec.ts-snapshots/*-{project}-{platform}.png` (`snapshotPathTemplate` includes `{platform}`) |
| Committed baselines | win32 only (see `goals/loop-v44-visreg/STATE.md`) |
| Run (local) | `cd frontend && npx playwright test --project=visreg` |
| Update baselines | `npx playwright test --project=visreg --update-snapshots` |
| CI functional e2e | `npx playwright test --project=chromium` — **`testIgnore`s visreg** |

Routes covered (both themes × desktop + 375px): `/`, market detail, empty
`/portfolio`, `/leaderboard`, `/eval`, `/admin/observability`. Visreg project
runs **first** locally so shared e2e SQLite is still pristine before chromium
journeys mutate it.

---

## 12. CI workflows

Workflows live under `.github/workflows/`. Branch filters in-tree currently
target historical integration branches (`loop3-agent-memory`,
`codex/alphaedge-base`) — operators adding new default branches must extend
`on.push` / `on.pull_request` lists deliberately.

| Workflow file | Purpose |
|---------------|---------|
| `ci-backend.yml` | `uv sync --extra dev`, pytest (backend), `PAPER_TRADING_ONLY=true` |
| `ci-frontend.yml` | `npm ci`, typecheck, lint (`--max-warnings=0`), Vitest |
| `ci-e2e.yml` | Local-stack Playwright **chromium** project only (visreg excluded); isolated SQLite; schedulers mostly disabled for speed |
| `demo-uptime.yml` | 15m prod wake + `verify_prod.py` (see §5A) |
| `calibration-autolab.yml` | Calibration / AutoLab job (when enabled) |
| `deploy-railway-backend.yml` | Railway deploy path |
| `deploy-hf-space.yml` / `deploy-koyeb-backend.yml` | Alternate/historical hosts |
| `azure-static-web-apps-*.yml` | Retired Azure SWA path — do not use as live frontend |

**CI e2e env posture (names only):** `PAPER_TRADING_ONLY=true`, temporary
`ADMIN_API_KEY` / `JWT_SECRET_KEY` for the job, SQLite URLs, Redis disabled
sentinel, most `SCHEDULER_*` and live feed flags **false** so the suite stays
deterministic.

Local full frontend gates (operator):

```text
cd frontend
npm run lint
npm run typecheck
npm run build
npm run test:e2e   # playwright; use --project=chromium to match CI
```

Orchestration gate for agents: `py -3.13 orchestration/gate.py` (exit 0 required
for “done”).

---

## Related docs

- [API reference](./api.md)
- [User guide](./user-guide.md)
- [Model methodology](./methodology.md)
- Visreg loop state: `goals/loop-v44-visreg/STATE.md`
- Deploy recipes: `docs/deploy/HUGGINGFACE_NEON.md`, `docs/deploy/KOYEB_NEON.md`,
  `docs/deploy/AZURE_VERCEL.md` (alternates / historical — not all are the live
  monitor target)
