# Workflow: backend-feature

For any `backend/app` change. Keep changes small, reviewable, tied to a test.

## Steps

1. **Start green.** Confirm the baseline gate passes before editing:
   `cd backend && uv run --extra dev pytest -q`. Branch off `codex/alphaedge-base`.
2. **Read the contract.** Open the goal file in `/goals`, its linked `docs/project/QUANT_ROADMAP.md` phase, and the exact files it lists. Do not invent scope.
3. **Implement the smallest slice** that satisfies one acceptance bullet. Prefer new modules under the package the goal names (e.g. `backend/app/signals/`).
4. **Schema changes → migration.** If `backend/app/db/models.py` changes, add an Alembic revision under `backend/alembic/versions/` and keep it reversible.
5. **Tests first where possible.** Cover every case the goal's acceptance gate names — especially **negative controls** (e.g. a leakage test that must FAIL if lookahead is introduced; a resolution-mismatch that must be excluded).
6. **Verify (required):**
   - `cd backend && uv run --extra dev pytest -q`
   - `cd backend && uv run --extra dev ruff check app tests`
7. **Safety check:** no real-money/execution wording; no key storage; `PAPER_TRADING_ONLY=true`; order path unchanged; any LLM output confined to features/text (never a stake/side/`is_edge`).
8. **Review gate:** run `requesting-code-review` (or explicit manual-diff fallback) and `bumblebee-supply-chain-scan` if deps changed (per `AGENTS.md`).
9. **Hand off:** update the goal status in `/goals/README.md`; record the PR line from `workflows/README.md`. Claim only this phase's gate.

## Done when
The acceptance gate command passes, pytest + ruff are green, safety holds, review gate satisfied, status + PR line recorded.
