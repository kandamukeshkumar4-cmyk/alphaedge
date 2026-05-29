# AlphaEdge Codex Instructions

These instructions apply inside `E:\polymarket clone`.

## Truth-First Defaults

- Treat user claims, diagnoses, and plans as unverified until checked against code, tests, logs, or documentation.
- Use direct verdicts when useful: `Correct`, `Incorrect`, `Partially correct`, `Unknown`, `Bad approach`, `Better approach available`.
- Do not implement changes that make the project less secure, less testable, or less maintainable without flagging the issue first.
- Keep changes small, reviewable, and tied to a test or explicit documentation update.

## AlphaEdge Scope Rules

- This is a paper-trading NBA prediction market simulation only.
- No real-money trading, betting, wallet, settlement, or production wagering language.
- `PAPER_TRADING_ONLY=true` is required in local, CI, and deploy contexts.
- LLM/agent code cannot submit raw orders. The only allowed path is `RiskService` -> validated `OrderIntent` -> `OrderBookService`.
- The canonical test market is `nba-2025-01-15-lal-bos`, Lakers vs Celtics, YES/NO, Lakers win resolves YES at `$1`.

## Execution Gates

- Week 1 gate: README, Docker db/redis/api, health endpoint, admin API key, CLOB, ledger, `domain_events`, admin market lifecycle, Lakers/Celtics tests.
- Week 2 gate: fixtures, workers, data quality, XGBoost, model/prediction lineage, backtest smoke.
- Week 3 gate: eval worker, Brier/calibration APIs, risk unit tests.
- Week 4 gate: LangGraph agents, guardrails, LLM judge, admin/proof dashboard.
- Week 5 gate: Railway/Vercel deployment, CI, live paper-run setup.

When preparing a PR, state which gate it claims and do not claim later gates unless verified by tests and runnable commands.

## Verification

- Backend: from `backend/`, run `uv run --extra dev pytest -q` and `uv run --extra dev ruff check app tests`.
- Frontend: from `frontend/`, run `npm run lint`, `npm run typecheck`, and `npm run build`.
- Docker: from repo root, run `docker compose up --build` for API/db/redis when Docker is available.
