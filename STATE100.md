# Loop 100 — Alpha Model Phase 3: Idea Generator

## Graph and guardrails

`idea_generator (proposal only) -> validator (deterministic checker) -> existing regime/constructor/decomposer tail -> AlphaRun state -> stop`.

- The generator emits only `name`, `description`, `required_inputs`, and
  `predicted_direction`; it has no `is_edge`, side, stake, order, or risk authority.
- `AlphaRun.result` and `AlphaRun.rejection_reasons` are the persistent state.
  Rejected hypothesis names from the trailing 30 days are excluded before a new
  proposal cycle.
- No migration is needed: `alpha_runs` is the current single-head persistence
  surface and already stores JSON research evidence.
- The router is already wired from `backend/app/main.py` via `alpha_router`;
  IG3 extends that existing public router only.

## Ticket state

| Ticket | Status | Proof |
| --- | --- | --- |
| IG1 | DONE | `3 passed`; `uv run --extra dev ruff check app tests` passed (2026-07-24) |
| IG2 | DONE | `5 passed`; `uv run --extra dev ruff check app tests` passed (2026-07-24) |
| IG3 | PENDING | — |
