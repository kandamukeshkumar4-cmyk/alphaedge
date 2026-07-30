# Lane D — bias-adjusted probability API (unblocks P11)

> Executor: Codex or Grok (Cursor), user's machine. Branch: `loop-d-bias-adjusted`
> (create from `codex/alphaedge-base`). Work ONLY in `backend/**` and this
> folder. Read `AGENTS.md` first. One ticket per iteration, then STOP —
> the orchestrator (Claude, PR #58 session) reviews and merges.

## Ticket D01

Expose the existing isotonic calibration (`backend/app/ml/calibration.py`,
currently internal-only) as an ADDITIVE field on the `/explain` response:

- Field: `calibrated_prob` (float | null), beside the existing `model_prob`
  and `market_implied`. Do not rename or remove anything.
- `null` when the calibrator has < BRIER_MIN_SAMPLE (30) resolved outcomes —
  honest empty, never a fabricated number.
- Fixture tests for BOTH states (enough samples → real value; too few → null).
- Document the exact response JSON in `goals/loop-d-bias-adjusted/API-NOTES.md`
  — the frontend P11 ticket integrates from it; field names are a contract.

## Guardrails

PAPER_TRADING_ONLY; order path untouched; no new HTTP fetchers; gate =
`uv run --extra dev pytest -q` + `uv run --extra dev ruff check app tests`
both green, output pasted into the LOOP LOG below. Never weaken a test.

## LOOP LOG

| iter | date | ticket | result | proof |
|------|------|--------|--------|-------|
