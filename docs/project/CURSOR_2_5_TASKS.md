# Cursor 2.5 Task Assignment

Owner: Cursor 2.5 executor  
Project manager/reviewer: Codex  
Repository: `E:\polymarket clone`  
Branch target: `codex/alphaedge-base`

## Current Verdict

Partially correct: the repo contains a working AlphaEdge base, but it already includes Week 2-4 scaffold files. Treat Week 1 CLOB/API as the first review gate and treat later-week modules as scaffold until their tests and docs prove production readiness.

## Task 1: Week 1 CLOB Gate

Goal: make the Week 1 PR independently reviewable.

Files to focus:
- `README.md`
- `docker-compose.yml`
- `backend/app/main.py`
- `backend/app/admin/routes.py`
- `backend/app/api/v1/routes.py`
- `backend/app/market/order_book.py`
- `backend/app/services/order_book_service.py`
- `backend/app/services/market_service.py`
- `backend/app/services/ledger_service.py`
- `backend/app/events/bus.py`
- `backend/app/db/models.py`
- `backend/alembic/versions/001_initial_schema.py`
- `backend/tests/test_orderbook_lakers_celtics.py`
- `backend/tests/test_orderbook_engine.py`

Steps:
1. Run `uv run --extra dev pytest backend/tests/test_orderbook_lakers_celtics.py backend/tests/test_orderbook_engine.py -q` from repo root.
2. If a test fails, fix the CLOB or service behavior, not the assertion, unless the assertion contradicts the product rules in `README.md`.
3. Run `uv run --extra dev ruff check app tests` from `backend/`.
4. Confirm `docker compose up --build` starts API, Postgres, and Redis with `/health` returning `paper_trading_only: true`.
5. Prepare a PR summary that claims only Week 1 behavior.

Acceptance:
- CLOB tests pass.
- Admin market create/lock/resolve routes require `X-Admin-API-Key`.
- `order_submitted`, `order_filled`, `market_locked`, and `market_resolved` emit `domain_events`.
- No real-money wording is introduced.

## Task 2: Later-Week Scaffold Audit

Goal: prevent scaffold code from being mistaken for a fully validated system.

Files to focus:
- `backend/app/backtesting/`
- `backend/app/ml/`
- `backend/app/eval/`
- `backend/app/risk/`
- `backend/app/agents/`
- `backend/app/workers/`
- `frontend/src/app/`

Steps:
1. Run the full backend suite with `uv run --extra dev pytest -q` from `backend/`.
2. Run frontend checks from `frontend/`: `npm run lint`, `npm run typecheck`, `npm run build`.
3. For each later-week module, add or update tests before claiming the corresponding week gate.
4. Keep any Gemini/LangGraph behavior behind risk validation and deterministic fallback paths.

Acceptance:
- Full test suite passes.
- Frontend build passes.
- Any unverified week remains documented as scaffold, not done.

## Task 3: GitHub Repo Setup

Goal: make the project shareable with CI and clean contribution surfaces.

Steps:
1. Confirm `git status --short` has only intended source, docs, fixture, and lockfile changes.
2. Create or use GitHub repo `kandamukeshkumar4-cmyk/alphaedge`.
3. Push branch `codex/alphaedge-base`.
4. Open a PR titled `AlphaEdge base scaffold`.
5. In the PR body, include verification output for backend tests, frontend lint/typecheck/build, and any Docker result.

Acceptance:
- Remote exists.
- CI workflow runs backend and frontend jobs.
- PR body does not claim unverified Week 2-5 completion.
