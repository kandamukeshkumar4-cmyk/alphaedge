# Lane E — resolved-count watcher surfacing (P10 progress)

> Executor: Qwen (NIM) or Gemini, user's machine. Branch: `loop-e-ab-watch`
> (create from `codex/alphaedge-base`). Work ONLY in `backend/**` and this
> folder. Read `AGENTS.md` first. One ticket per iteration, then STOP —
> the orchestrator (Claude, PR #58 session) reviews and merges.

## Ticket E01

Surface the A/B gate progress (resolved outcome count from
`backend/app/ml/ab_harness.py`, same sources as `/api/v1/track-record`'s
`n`) as an ADDITIVE field on the existing admin stats payload:

- Field: `resolved_outcomes_count` (int) + `ab_gate_threshold` (int, 100).
- NEVER flip the default model in this lane — the existing tests that
  assert `default_model_changed=false` and `ML_MODEL_TYPE=xgboost` must
  stay intact and passing.
- Tests: count reflects seeded resolutions; empty DB → 0 (honest empty).
- Document the field in `goals/loop-e-ab-watch/API-NOTES.md`.

## Guardrails

PAPER_TRADING_ONLY; order path untouched; gate =
`uv run --extra dev pytest -q` + `uv run --extra dev ruff check app tests`
both green, output pasted into the LOOP LOG below. Never weaken a test.

## LOOP LOG

| iter | date | ticket | result | proof |
|------|------|--------|--------|-------|
