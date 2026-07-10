# Opus 4.8 Polish Loop — assignment wrapper (2026-07-09)

> Executor: Claude Opus 4.8. Worktree: `E:\polymarket-worktrees\loop-opus-polish`
> (branch `loop-opus-polish`). Work ONLY there.

The loop itself is `goals/build-loop-polish/STATE.md` (tickets P01–P12).
Follow its iteration protocol, gate, and maker/checker split exactly, with
these parallel-run overrides:

## SCOPE FENCE (overrides — violating = failed iteration, revert)

- You may edit ONLY: `frontend/**`, `goals/build-loop-polish/**`, and
  `goals/loop-opus-polish/**`.
- NEVER edit `backend/**` — a parallel Grok loop owns it in another worktree.
  - P10: do NOT implement (its watcher/harness is backend; reassigned to the
    backend loop as G06). Skip it.
  - P11: frontend display layer only; if it needs a backend field that doesn't
    exist yet, mark BLOCKED-ON-BACKEND (G05) in the log and move on.
  - P07: consume the existing `/api/v1/calibration` (or the upcoming
    `/api/v1/track-record` per `goals/loop-grok-backend/API-NOTES.md`) —
    read that file, never edit it.
- All work commits to branch `loop-opus-polish`. Do not push, do not merge —
  the orchestrator (Claude, main thread) reviews and merges.
- Gate for this loop = the frontend gate from build-loop-polish STATE.md
  (typecheck, lint, vitest, build, browser render evidence). Backend pytest is
  NOT your gate (you can't touch backend).

## Order

P01 → P02 → P03 → P04 → P05 → P06 → P07 → P08 → P09 → P12 → (P11 if unblocked).
One ticket per iteration. Update the LOOP LOG in build-loop-polish/STATE.md
with evidence + AutoLab line each time. Commit `feat(polish): <ticket> <summary>`.
