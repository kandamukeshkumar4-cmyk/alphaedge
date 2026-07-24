# STATE90B — V90 E-B onboarding (fix pass)

**Worktree:** `E:/polymarket-worktrees/loop90-onboard`  
**Branch:** `loop90/onboard`  
**Charter paths only:** `frontend/src/app/onboarding/**`, `frontend/src/components/onboarding/**`, `frontend/src/lib/onboarding.ts`, `frontend/e2e/onboarding.spec.ts`, `STATE90B.md`  
**Do not touch:** `layout.tsx` (already mounts `<OnboardingGate/>`).  
**Images:** not read.

AutoLab: not applicable (no iterative measure — proof/test gap fix).

---

## O1 — first-run storage (`frontend/src/lib/onboarding.ts`)

**Impl commit:** `d0df5d9 feat(loop90): O1 — add first-run onboarding storage`  
**Fix commit:** `9f619cf fix(loop90): O-fix2 — cover SSR and private-mode onboarding helpers in vitest`

- Key: `ae_onboarded_v1`
- Helpers: `isFirstRun()` / `markOnboarded()` / `resetOnboarding()`
- SSR / private-mode: no `window` or throwing/missing `localStorage` ⇒ not first-run; helpers no-throw

### Proof — vitest (F2)

```text
$ cd frontend && npx vitest run

 RUN  v4.1.8 E:/polymarket-worktrees/loop90-onboard/frontend

 Test Files  95 passed (95)
      Tests  536 passed (536)
   Start at  21:31:16
   Duration  23.43s (transform 6.64s, setup 0ms, import 66.16s, tests 3.70s, environment 24ms)

VITEST_EXIT:0
```

Targeted onboarding file (6 cases: first-run / mark / reset / SSR / missing storage / private-mode throw):

```text
$ npx vitest run src/app/onboarding/onboarding.test.ts

 Test Files  1 passed (1)
      Tests  6 passed (6)
   Duration  1.31s
VITEST_ONBOARD_EXIT:0
```

---

## O2 — Gate + Tour (layout mount unchanged)

**Impl commit:** `75fcda4 feat(loop90): O2 — add first-run onboarding tour`  
**Fix commit:** `0d063a9 fix(loop90): O-fix3 — clear localStorage and assert post-Skip reload in E2E`

- `<OnboardingGate/>` client; first-run shows `<OnboardingTour/>`
- Welcome copy exact; 4 steps Terminal / Skills / Scanners / Screener
- Skip / ESC / finish → `markOnboarded()`; progress dots
- E2E clears prior `ae_onboarded_v1`, asserts overlay, Skip sets flag, reload shows no overlay
- Stale `:31099` Internal Server Error / webpack crash → killed PID, restarted `npx next dev -H 127.0.0.1 -p 31099` before E2E

### Proof — Playwright (F3)

```text
$ E2E_SKIP_WEBSERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:31099 npx playwright test e2e/onboarding.spec.ts --project=chromium

Running 1 test using 1 worker
  ok 1 [chromium] › e2e\onboarding.spec.ts:6:7 › first-run onboarding › shows the tour and Skip persists completion (6.0s)

  1 passed (6.9s)
PW_EXIT:0
```

---

## O3 — `/onboarding` replay route

**Impl commit:** `ac67d1e feat(loop90): O3 — add replayable onboarding route`

- Client page: `resetOnboarding()` then render tour
- Gate skips when `pathname.startsWith("/onboarding")`
- Build lists `○ /onboarding` (see F4 build paste)

---

## F4 — full frontend proof set (re-verify)

```text
$ npm run typecheck
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
TYPECHECK_EXIT:0
```

```text
$ npm run lint
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
LINT_EXIT:0
```

```text
$ npm run build
> alphaedge-frontend@0.1.0 build
> next build

   ▲ Next.js 15.5.18
 ✓ Compiled successfully in 26.1s
 ✓ Generating static pages (114/114)

Route (app)                                         Size  First Load JS
├ ○ /onboarding                                  4.89 kB         147 kB
…

BUILD_EXIT:0
```

(typecheck re-run after build also exit 0)

---

## Fix commits (this pass)

```text
0d063a9 fix(loop90): O-fix3 — clear localStorage and assert post-Skip reload in E2E
9f619cf fix(loop90): O-fix2 — cover SSR and private-mode onboarding helpers in vitest
```

`git log -1` after O-fix1/O-fix4 STATE commits will supersede the tip line above.

## Verdict

O1–O3 implementation retained; audit gaps closed: STATE present with pasted proofs, vitest covers SSR/private-mode and full suite green, E2E first-run path green after clean `:31099` restart, typecheck/lint/build green.

No push. No ESCALATION.
