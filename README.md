# AlphaEdge

**AlphaEdge** is a **paper-trading** prediction-market **simulation** for NBA,
broader sports, and election markets. It combines a central limit order book
(CLOB), venue market data, XGBoost modeling, LangGraph agents, risk controls,
and continuous evaluation (Brier, calibration, drift, CLV).

> **Paper-trading disclaimer:** Simulated funds only. No cash deposits,
> withdrawals, payment rails, or real-money execution.

**`PAPER_TRADING_ONLY=true` is required** in local, CI, and production.
Settings validation refuses to boot when the flag is false.

**Order safety:** LLM/agent code cannot submit raw orders. The only agent path is
`RiskService` → validated `OrderIntent` → `OrderBookService`. Human UI paper
trades use a separate JWT `PaperOrder` ledger (also paper-only).

---

## Documentation (Loop V19)

| Doc | Contents |
|-----|----------|
| [docs/api.md](docs/api.md) | Verified HTTP/WebSocket API reference |
| [docs/user-guide.md](docs/user-guide.md) | Signup, discover, paper trade, portfolio, track record lifecycle |
| [docs/operations.md](docs/operations.md) | Deploy (Railway/Vercel), env names, migrations, monitoring |
| [docs/methodology.md](docs/methodology.md) | Forecast engine, walk-forward CLV gate, leakage, drift, A/B |

---

## Canonical example market

| Field | Value |
|-------|--------|
| Title | Lakers vs Celtics |
| Question | Will the Lakers win? |
| Outcomes | YES / NO |
| Slug | `nba-2025-01-15-lal-bos` |
| Resolve | Lakers win → YES @ $1 |

Seeded on API startup and via `scripts/seed_nba_markets.py`.

---

## Production stack (monitored)

Uptime CI (`.github/workflows/demo-uptime.yml`) targets:

| Layer | Host role |
|-------|-----------|
| Backend API | Railway (`*.up.railway.app`) — Docker build from `backend/` |
| Frontend | Vercel — `alphaedge-frontend-three.vercel.app` |
| Database | Postgres (`DATABASE_URL` / `DATABASE_URL_SYNC`; Neon and Railway Postgres both used historically) |

Deploy details, env **names** (no secret values), migrations, and rollback notes:
**[docs/operations.md](docs/operations.md)**.

Hugging Face Spaces, Koyeb, and Azure recipes under `docs/deploy/` are
**alternate/legacy** paths — not the default monitor target. The old Azure
Static Web Apps frontend host is **dead (404)** and must not be used.

Verify production (read-only):

```bash
py -3.13 scripts/verify_prod.py --api https://<api-host> --frontend https://alphaedge-frontend-three.vercel.app
```

---

## Quick start (local)

**Prerequisites:** Docker Desktop (for compose), **Python 3.11+** (3.13 OK),
**Node 18+**, [`uv`](https://github.com/astral-sh/uv) recommended for the backend.

### 1. Environment

```bash
cp .env.example .env
# Ensure PAPER_TRADING_ONLY=true
```

### 2a. Full API stack with Docker (simplest)

```bash
docker compose up --build
```

Migrations run on boot (`alembic upgrade head`), then uvicorn on port 8000.

| URL | Purpose |
|-----|---------|
| http://localhost:8000 | API |
| http://localhost:8000/health | Health (`paper_trading_only` should be true) |
| http://localhost:8000/docs | OpenAPI UI |
| http://localhost:3000 | Frontend (after step 3) |

Admin header: `X-Admin-API-Key` (compose default name `ADMIN_API_KEY`; local
default is for **dev only** — never reuse in production).

Optional worker profile:

```bash
docker compose --profile full up --build
```

### 2b. Backend without Docker API container

```bash
# Postgres + Redis still needed (compose db/redis services, or local installs)
cd backend
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Point `DATABASE_URL` / `DATABASE_URL_SYNC` / `REDIS_URL` at your instances
(see `.env.example`).

### 3. Frontend

```bash
cd frontend
npm install
# optional: echo NEXT_PUBLIC_API_URL=http://localhost:8000 > .env.local
npm run dev
```

### 4. Tests

```bash
# Backend
cd backend
uv sync --extra dev
uv run --extra dev pytest -q
uv run --extra dev ruff check app tests

# Frontend unit + type + lint + build
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build

# End-to-end (Playwright)
cd frontend
npm run test:e2e
```

Windows note: if `python` is wrong, use `py -3.13 -m …` equivalents for scripts
outside `uv run`.

### Optional extras

```bash
python scripts/seed_nba_markets.py   # API must be up
python scripts/run_backtest.py

cd extension && npm install && npm test && npm run build   # AlphaEdge Mirror MV3
```

---

## Architecture (high level)

```text
Venues / fixtures → features → XGBoost (+ calibration)
                              → walk-forward CLV gate
CLOB / paper ledgers ← RiskService ← agents (no raw LLM orders)
Eval → Brier / ECE / drift / track-record (real resolutions only)
```

| Week gate | Theme |
|-----------|--------|
| 1 | CLOB, ledger, domain events, admin API |
| 2 | Fixtures, workers, XGBoost, backtest |
| 3 | Eval, Brier/calibration APIs, risk tests |
| 4 | LangGraph agents, guardrails, dashboards |
| 5 | Deploy, CI, live paper-run |

Quant roadmap goals live under `goals/` + `workflows/` (see `goals/README.md`).

---

## Repository layout

```text
alphaedge/
├── docker-compose.yml
├── docs/                 # api, user-guide, operations, methodology, deploy/*
├── backend/              # FastAPI, Alembic, workers, ML
├── frontend/             # Next.js app
├── extension/            # Mirror skill tracker (optional)
├── scripts/              # deploy + verify_prod helpers
└── orchestration/        # multi-agent gates
```

Backend-specific notes: [backend/README.md](backend/README.md)  
Frontend-specific notes: [frontend/README.md](frontend/README.md)

---

## Optional API keys (not required for local demo)

Names only — never commit values:

| Variable | Purpose |
|----------|---------|
| `LLM_API_KEY` / `NIM_API_KEY` / provider keys | Analyst + assistant LLM |
| `GEMINI_API_KEY` | Drift judge / reasoning fallbacks |
| `LANGSMITH_API_KEY` | Agent tracing |
| `ODDS_API_KEY` | Live odds (fixtures used when unset) |
| `ENSEMBLE_ENABLED` | Multi-model ensemble router (default on; degrades safely) |
| `KALSHI_WS_ENABLED` / `POLYMARKET_WS_ENABLED` | Venue price websockets (default on) |
| `SCHEDULER_*_ENABLED` | In-process scheduled jobs when Redis worker is disabled |
| `ML_MODEL_TYPE` | Deployed classifier type (`xgboost` default; never auto-flipped by A/B) |
| `DRIFT_ALARM_ENABLED` | Calibration drift alerts (default off) |

Full operator table: [docs/operations.md](docs/operations.md).

---

## Resume bullet

> Architected AlphaEdge, an event-driven AI paper-trading platform using
> FastAPI, Redis workers, XGBoost, LangGraph, and Postgres to simulate sports
> and election prediction markets with real CLOB execution, risk controls,
> Brier scoring, calibration tracking, and drift monitoring.

---

*Paper-trading simulation with simulated funds only.*
