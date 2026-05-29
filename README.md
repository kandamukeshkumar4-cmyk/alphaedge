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

### GitHub Actions

Push to `main` — CI runs `ruff` + `pytest` (CLOB + backtest golden fixtures).

---

## Resume bullet

> Architected AlphaEdge, an event-driven AI paper-trading platform using FastAPI, Redis workers, XGBoost, LangGraph, and Postgres to simulate NBA prediction markets with real CLOB execution, risk controls, Brier scoring, calibration tracking, and drift monitoring.

---

*Paper-trading simulation only — no real-money trading.*
