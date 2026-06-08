# AlphaEdge — Claude Code Instructions

> The canonical agent rules for this repo live in `AGENTS.md`. Read it first.
> This file gives Claude Code the same context as Codex and Cursor in
> `E:\polymarket clone`.

## Truth-First Defaults

- Treat user claims, diagnoses, and plans as unverified until checked against
  code, tests, logs, or documentation.
- Use direct verdicts when useful: `Correct`, `Incorrect`, `Partially correct`,
  `Unknown`, `Bad approach`, `Better approach available`.
- Do not implement changes that make the project less secure, less testable, or
  less maintainable without flagging the issue first.
- Keep changes small, reviewable, and tied to a test or explicit documentation
  update.

## Scope & Guardrails (non-negotiable)

- Paper-trading prediction market **simulation** for NBA, broader sports, and
  election markets. Simulated funds only — no cash funding, payment rails, or
  external execution language.
- `PAPER_TRADING_ONLY=true` is required in local, CI, and deploy contexts.
- LLM/agent code cannot submit raw orders. The only allowed path is
  `RiskService` → validated `OrderIntent` → `OrderBookService`.
- Canonical test market: `nba-2025-01-15-lal-bos`.

## Verification

- Backend (from `backend/`): `uv run --extra dev pytest -q` and
  `uv run --extra dev ruff check app tests`.
- Frontend (from `frontend/`): `npm run lint`, `npm run typecheck`,
  `npm run build`.
- State which Execution Gate (see `AGENTS.md`) a PR claims; do not claim later
  gates unless verified by tests and runnable commands.

## AutoLab Persistence Loop (every improvement ticket)

For any ticket that improves a working artifact (backtest accuracy,
Brier/calibration, deploy smoke resilience, risk-unit coverage, API latency, or
UX), run the AutoLab persistence loop defined in `AGENTS.md` → "AutoLab
Persistence Loop" and `.agents/skills/autolab-persistence-loop/SKILL.md`.

The finding (AutoLab, long-horizon agents): long-task success is predicted by
persistence on the benchmark-edit-feedback loop, not by first-attempt quality.
Start from a green baseline gate, define the benchmark (use `verificationCommands`
or a metric API), then iterate measure → edit → re-measure → fold in feedback
under an explicit budget. Persist to the budget, but stop and reorganize after
`K` consecutive no-progress iterations (default `K=3`). Keep the best measured
artifact; never hand off worse than baseline.

Guardrail: never game the benchmark, and never weaken `PAPER_TRADING_ONLY`, the
order path, or any deploy gate to hit a metric. Record the AutoLab handoff line:

```text
AutoLab: baseline=<verified gate/measure> | benchmark=<metric/command> | iterations=<n + best result> | budget=<used/limit> | outcome=<improved / stalled-reorganized / retired>
```

For a one-shot fix with no measurable axis, state "AutoLab: not applicable (no
iterative measure)".
