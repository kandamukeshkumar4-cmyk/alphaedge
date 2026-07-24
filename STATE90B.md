# Loop 90B — onboarding proof

Status: O1–O3 implemented and committed. Frontend gate PASS. The full
repository gate was attempted twice and timed out at the external command
caps, so this worktree does not claim a full-repo gate PASS.

## Charter

Changed paths only:

- `frontend/src/lib/onboarding.ts`
- `frontend/src/app/onboarding/onboarding.test.ts`
- `frontend/src/components/onboarding/OnboardingGate.tsx`
- `frontend/src/components/onboarding/OnboardingTour.tsx`
- `frontend/src/app/layout.tsx` (one `OnboardingGate` mount)
- `frontend/src/app/onboarding/page.tsx`
- `frontend/e2e/onboarding.spec.ts`
- `STATE90B.md`

Pre-existing untracked `luna-*` and `grok-*` files were preserved and not
touched.

## Tickets

### O1 — first-run storage

Commit: `d0df5d9 feat(loop90): O1 — add first-run onboarding storage`

`npx vitest run src/app/onboarding/onboarding.test.ts`

```text
Test Files  1 passed (1)
Tests       3 passed (3)
```

`npm run typecheck`

```text
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
```

`npm run lint`

```text
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
```

### O2 — client tour and gate

Commit: `75fcda4 feat(loop90): O2 — add first-run onboarding tour`

`npm run typecheck`

```text
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
```

`npm run lint`

```text
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
```

### O3 — replay route

Commit: `ac67d1e feat(loop90): O3 — add replayable onboarding route`

`npm run typecheck`

```text
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
```

`npm run lint`

```text
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
```

## Final proof

`git log -1 --oneline`

```text
ac67d1e (HEAD -> loop90/onboard) feat(loop90): O3 — add replayable onboarding route
```

`npm run build`

```text
> alphaedge-frontend@0.1.0 build
> next build

▲ Next.js 15.5.18
✓ Compiled successfully in 60s
✓ Generating static pages (114/114)
Route: ○ /onboarding  4.89 kB  147 kB
```

`E2E_SKIP_WEBSERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:31099 npx playwright test e2e/onboarding.spec.ts --project=chromium`

PowerShell equivalent used:

```text
Running 1 test using 1 worker
ok 1 [chromium] › e2e\onboarding.spec.ts › first-run onboarding › shows the tour and Skip persists completion (10.2s)
1 passed (40.3s)
```

Assertions: first-run overlay is visible, welcome copy is present, Skip hides
the overlay, and `localStorage.getItem("ae_onboarded_v1")` becomes `"true"`.

## Deterministic gate

`py -3.13 orchestration/gate.py --frontend-only`

```text
PASS frontend typecheck (exit 0)
Test Files  95 passed (95)
Tests       536 passed (536)
PASS frontend test (exit 0)
PASS frontend build (exit 0)
=== GATE VERDICT ===
PASS: all checks green
```

`py -3.13 orchestration/gate.py` was also run twice. Attempt 1 timed out at
188981 ms / exit 124; attempt 2 timed out at 904143 ms / exit 124. No full-gate
PASS is claimed. No third attempt was made; no source retry is warranted for a
repository-wide timeout outside this frontend charter.

Supply-chain scan: not applicable; no package manifest, lockfile, dependency
loader, or deployment image changed.
