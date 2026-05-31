# AlphaEdge

**AlphaEdge** is a paper-trading NBA prediction market **simulation** for research and portfolio demonstration. It combines a real central limit order book (CLOB), NBA odds ingestion, XGBoost modeling, LangGraph agents, risk controls, and continuous evaluation (Brier, calibration, drift).

> **Paper-trading disclaimer:** This project is a paper-trading simulation for research and portfolio demonstration only. No real-money trading, betting, or settlement is supported.

`PAPER_TRADING_ONLY=true` is required.

**Safety:** LLM agents can explain and adjust confidence, but **cannot bypass RiskAgent**. Orders flow only through `RiskService` → validated `OrderIntent` → `OrderBookService` — never from raw LLM text.

---

## Canonical example: Lakers vs Celtics

| Field | Value |
|-------|--------|
| Title | Lakers vs Celtics |
| Question | Will the Lakers win? |
| Outcomes | YES / NO |
| Slug | `nba-2025-01-15-lal-bos` |
| Resolve | Lakers win → YES @ $1 |

This market is seeded automatically on API startup (and via `scripts/seed_nba_markets.py`).

---

## Quick start (local)

**Prerequisites:** Docker Desktop (running), Python 3.12+, Node 18+

```bash
# 1. Environment
cp .env.example .env

# 2. Start API + Postgres + Redis (migrations run on boot)
docker compose up --build
```

| URL | Purpose |
|-----|---------|
| http://localhost:8000 | API root |
| http://localhost:8000/health | Health check |
| http://localhost:8000/docs | OpenAPI / Swagger |
| http://localhost:3000 | Frontend (after `npm run dev`) |

Admin routes require header `X-Admin-API-Key` (default in compose: `dev-admin-key`).

### Full stack (background worker)

```bash
docker compose --profile full up --build
```

### Run tests (no Docker required)

```bash
cd backend
python -m pip install -e ".[dev]"
pytest -v
```

On Windows, if `python` points to a venv without pip, use: `py -3.13 -m pip install -e ".[dev]"` then `py -3.13 -m pytest -v`.

### Frontend

```bash
cd frontend
npm install
npm run build    # production build
npm run dev      # dev server at http://localhost:3000
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local` for live API calls.

### Seed Lakers market manually (optional)

```bash
# API must be running
python scripts/seed_nba_markets.py
```

### Backtest

```bash
python scripts/run_backtest.py
```

---

## Architecture

```text
CLOB → Backtest → XGBoost → Eval → Risk → Agents
```

| Week | Deliverable |
|------|-------------|
| 1 | CLOB, ledger, domain_events, admin API |
| 2 | Fixtures, workers, XGBoost, backtest proof |
| 3 | Eval worker, Brier/calibration APIs, risk tests |
| 4 | LangGraph, guardrails, admin + proof dashboard |
| 5 | Deploy configs, CI, worker in compose |

---

## Repository layout

```text
alphaedge/
├── docker-compose.yml
├── fixtures/
├── backend/
├── frontend/
└── scripts/
```

---

## Optional API keys (not required for local demo)

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | LLM drift judge + agent reasoning (falls back to heuristics without it) |
| `LANGSMITH_API_KEY` | Agent tracing |
| `ODDS_API_KEY` | Live NBA odds (fixtures used when unset) |

---

## Deploy (Week 5)

### Railway (API + worker)

- API: `railway.toml` at repo root
- Worker: `backend/railway.worker.toml` — `python -m app.workers.main`
- Env: `DATABASE_URL`, `REDIS_URL`, `ADMIN_API_KEY`, `PAPER_TRADING_ONLY=true`
- Run migrations: `alembic upgrade head`

### Vercel (frontend)

- Root directory: `frontend/`
- Env: `NEXT_PUBLIC_API_URL=https://your-api.railway.app`

### Azure Static Web Apps frontend

The frontend is deployed as a static Next.js export on Azure Static Web Apps:

```text
https://proud-meadow-01b42b810.7.azurestaticapps.net
```

Set `NEXT_PUBLIC_API_URL` in GitHub Actions secrets before rebuilding the static frontend.

The live demo also includes a small Azure Static Web Apps managed API under `api/`.
It serves `/api/health`, `/api/v1/markets`, and `/api/v1/eval/aggregates` from the
same free Static Web App so the public portfolio pages stay usable even when a
separate container backend is blocked by free-tier quota or payment verification.

### Koyeb + Neon backend fallback

Use this when Azure Container Apps/App Service quotas block the backend and Vercel is unavailable:

- Koyeb Free Web Service for the FastAPI Docker backend
- Neon Free Postgres for `DATABASE_URL` and `DATABASE_URL_SYNC`
- Existing Azure Static Web Apps frontend remains live

See `docs/deploy/KOYEB_NEON.md`.

There is also a manual GitHub Actions workflow, `Deploy Backend to Koyeb`, for running the Koyeb deploy after adding the required repository secrets.

After creating the Neon DB and Koyeb token, `scripts/set_koyeb_neon_secrets.ps1` can set the required GitHub secrets and optionally trigger the deploy workflow.

Use `scripts/verify_koyeb_neon_ready.ps1` to verify Koyeb secrets, backend health,
canonical market data, and the frontend API URL after deployment.

### Hugging Face Spaces + Neon backend fallback

Use this when the Koyeb account flow requires payment verification but you still need a free/no-card public backend for the portfolio demo:

- Hugging Face Docker Space for the FastAPI backend
- Neon Free Postgres for `DATABASE_URL` and `DATABASE_URL_SYNC`
- Existing Azure Static Web Apps frontend remains live

Current public API:

```text
https://mukeshkumarkanda-alphaedge-api.hf.space
```

See `docs/deploy/HUGGINGFACE_NEON.md`.

### Azure for Students + Vercel

See `docs/deploy/AZURE_VERCEL.md` for the free-tier-oriented Azure Container Apps/PostgreSQL backend script and Vercel frontend deploy script.

### GitHub Actions

Push to `main` — CI runs `ruff` + `pytest` (CLOB + backtest golden fixtures).

---

## Resume bullet

> Architected AlphaEdge, an event-driven AI paper-trading platform using FastAPI, Redis workers, XGBoost, LangGraph, and Postgres to simulate NBA prediction markets with real CLOB execution, risk controls, Brier scoring, calibration tracking, and drift monitoring.

---

*Paper-trading simulation only — no real-money trading.*
