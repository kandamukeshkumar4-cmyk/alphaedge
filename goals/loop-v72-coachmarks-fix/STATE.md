# Loop V72 — Coach-marks interaction blocking + visreg · STATE

Worktree: `E:/polymarket-worktrees/loop72-coach` · branch `loop72/coachmarks`
Scope: **frontend only**. Binding: `GOAL.md`. Never push/merge. Never touch backend.

## Ticket status

| Ticket | Status | Evidence |
|---|---|---|
| C1 CoachMarks never block (pointer-events + mobile collapse) | **DONE** | `9aac638` |
| C2 E2e hygiene (seed seen + first-visit spec) | **DONE** | `8aa7914` |
| C3 Visreg regenerate stale home baselines | **DONE** | `5d1f9b7` (4 home PNGs) |
| C4 Run previously-failing specs + visreg | **DONE** | counts below |

## Exit

**C1–C4 DONE.** Branch `loop72/coachmarks` only — no push/merge.

## C1 notes

- Wrapper `pointer-events-none`; `pointer-events-auto` only on interactive controls.
- Narrow (`max-width: 1023px`): auto-collapse to a "Tips" chip above bottom nav;
  expanded card docks at `top-20` so it cannot cover mobile primary CTAs.
- Dismiss still writes `alphaedge.coachmarks.v1` and persists across reloads.

## C2 notes

- `skipOnboarding` now also seeds `alphaedge.coachmarks.v1`.
- New `e2e/coachmarks.spec.ts` deliberately leaves the flag unset and asserts
  first-visit show → Got it → persistent dismiss.

## C3 notes

- Regenerated only the four home baselines that changed under V62 redesign:
  `home-{dark,light}-{desktop,mobile375}-visreg-win32.png`.
- Spot-checked: home hero / Predict·Track·Prove loops match intended design;
  pink regions are stable-shot masks (sticky ticker), not coach-marks.
- Other 20 visreg surfaces unchanged (passed without rewrite).

## C4 verification (once)

```text
cd frontend
npx playwright test e2e/trade.spec.ts e2e/social.spec.ts e2e/notifications.spec.ts \
  e2e/mobile.spec.ts e2e/admin-eval.spec.ts e2e/visreg.spec.ts e2e/coachmarks.spec.ts \
  --reporter=line

Running 34 tests using 1 worker
  34 passed (3.8m)
EXIT=0
```

| suite | passed | failed |
|---|---:|---:|
| visreg (24) | 24 | 0 |
| admin-eval | 1 | 0 |
| coachmarks (first-visit) | 1 | 0 |
| mobile Q6 | 4 | 0 |
| notifications | 1 | 0 |
| social | 1 | 0 |
| trade | 2 | 0 |
| **total** | **34** | **0** |

Previously failing surfaces (trade, social, notifications, admin-eval, 3× mobile Q6
tap journeys) no longer hit `subtree intercepts pointer events` from
`aside[aria-label=Getting started]`.

## LOOP LOG

| loop | date | result | proof |
|------|------|--------|-------|
| V72 | 2026-07-17 | DONE — C1–C4 | PW 34 passed / 0 failed (3.8m); gate --frontend-only PASS |

### Gate paste

```text
py -3.13 orchestration/gate.py --frontend-only
PASS frontend typecheck (exit 0)
PASS frontend test (exit 0) — 83 files, 484 tests
PASS frontend build (exit 0)
=== GATE VERDICT ===
PASS: all checks green
```

AutoLab: not applicable (no iterative measure — one-shot interaction fix)
