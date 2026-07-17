# loop-v64-visreg — STATE

## Status
| Finding | Verdict | Fix |
|---------|---------|-----|
| mobile375/dark admin-observability Save Key timeout | **DONE** — test-helper gap (not app bug) | `readyObservability` hydration-safe key entry |

## Diagnosis
**Cause: (b) test-helper gap**, not a real mobile UI bug.

- App (`frontend/src/app/admin/layout.tsx`): Save Key is correctly
  `disabled={!draftKey.trim()}` on a memory-only controlled input. No change.
- Helper (`readyObservability` in `visreg.spec.ts`): filled `#admin-api-key`
  via `pressSequentially` then clicked Save without waiting for the button to
  enable. On slow mobile mounts, fill can race React hydration — DOM value
  briefly matches while `draftKey` is still `""`, so Save stays disabled and
  Playwright `.click()` actionability waits until the 180s test timeout.
  Serial suite then aborted → 6 did-not-run.

## Fix (smaller surface)
`frontend/e2e/visreg.spec.ts` only:
- wait for input visible
- retry fill up to 3× until Save is enabled (hydration race)
- `expect(save).toBeEnabled` before click (same pattern as admin-eval)

No app / admin-key memory-only handling changes.

## Verification (once)
```text
cd frontend
npx playwright test e2e/visreg.spec.ts --reporter=line

Running 24 tests using 1 worker
  24 passed (4.2m)
EXIT=0
```

| metric | before (loop54 full suite note) | after (this run) |
|--------|--------------------------------:|-----------------:|
| total | 24 visreg (suite aborted mid-serial) | 24 |
| passed | failed at mobile375/dark admin-observability | **24** |
| failed | 1 | **0** |
| did-not-run | 6 (light mobile surfaces) | **0** |

Including the original failure surface:
`mobile375 / dark › admin-observability` — **passed**.

## LOOP LOG
| loop | date | result | proof |
|------|------|--------|-------|
| V64 | 2026-07-17 | DONE — helper gap fixed | visreg 24 passed / 0 failed (4.2m) |

## Scope / non-goals
- Max 1 finding — STOP after this.
- Never push/merge.
- No `frontend/src` edits; admin key remains memory-only.

AutoLab: not applicable (no iterative measure — one-shot flake fix)
