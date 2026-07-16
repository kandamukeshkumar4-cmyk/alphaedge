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
| `SCHEDULER_WHALE_REFRESH_ENABLED` | Whale refresh |
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
| Migration deploy fail | `alembic heads` multi-head? pre-deploy logs |
| Metrics scrape 401 | Admin key or `METRICS_TOKEN` |
| JWT/admin boot fail in prod | Default secrets rejected when `APP_ENV` is production/staging |

---

## Related docs

- [API reference](./api.md)
- [User guide](./user-guide.md)
- [Model methodology](./methodology.md)
- Deploy recipes: `docs/deploy/HUGGINGFACE_NEON.md`, `docs/deploy/KOYEB_NEON.md`,
  `docs/deploy/AZURE_VERCEL.md` (alternates / historical — not all are the live
  monitor target)
