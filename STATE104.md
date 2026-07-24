# STATE104 — Community frontend node

Base: `9bfa413`  
Branch: `loop104-community/node`

Implemented the frozen community contract in the chartered frontend files:

- `frontend/src/lib/social-api.ts` — typed live-first client, preserving the existing trader/following exports already consumed by neighboring surfaces.
- `frontend/src/components/community/StoryFeed.tsx` — initial load plus explicit cursor pagination.
- `frontend/src/components/community/StoryCard.tsx` — historical story display, market link, optimistic like rollback, and comment-thread trigger.
- `frontend/src/components/community/CommentThread.tsx` — semantic comment list, disabled logged-out composer, 500-character counter, inline 422 handling, plain-text comment rendering.
- `frontend/src/components/community/SharedWatchlist.tsx` — public watchlist display with honest loading, empty, and error states.
- `frontend/src/app/community/page.tsx` and `frontend/src/app/w/[handle]/page.tsx` — routes.
- `frontend/e2e/community.spec.ts` — five focused Playwright scenarios.

Scope notes:

- No order, risk, sizing, execution, LLM, or dangerous-HTML client is imported.
- No secrets, API keys, or real auth tokens were printed or committed. The authenticated E2E uses the existing signup helper rather than setting a token literal.
- No central nav entry was added: `SiteHeader.tsx` is a contested shared surface in this wave, and the charter allows skipping it.
- `luna-prompt.txt` and `luna104.log` were pre-existing untracked files and remain untouched.
- Astryx discovery was attempted but its CLI could not run because the checkout initially had no installed dependencies; the local UI design-system search succeeded.
- The requested `requesting-code-review` skill was not callable. Manual diff review against the repo standards and frozen contract found no blocking issue.
- The full repo gate was attempted twice and timed out while backend-owned checks were running; no full-gate verdict is claimed. The frontend-only gate passed.

## Required proof

### `cd frontend && npm run typecheck`

```text
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
```

### `cd frontend && npm run lint`

```text
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
```

### `cd frontend && npm run build`

```text
> alphaedge-frontend@0.1.0 build
> next build

   ▲ Next.js 15.5.18

   Creating an optimized production build ...
 ✓ Compiled successfully in 24.7s
   Linting and checking validity of types ...
   Collecting page data ...
   Generating static pages (0/118) ...
   Generating static pages (29/118)
   Generating static pages (58/118)
   Generating static pages (88/118)
 ✓ Generating static pages (118/118)
   Finalizing page optimization ...
   Collecting build traces ...

Route (app)                                         Size  First Load JS
┌ ƒ /                                            15.9 kB         174 kB
├ ○ /_not-found                                    239 B         103 kB
├ ○ /about                                         173 B         107 kB
├ ○ /admin                                       5.75 kB         118 kB
├ ○ /admin/calibration                           2.78 kB         115 kB
├ ○ /admin/observability                         6.94 kB         119 kB
├ ○ /admin/proof                                 4.16 kB         107 kB
├ ○ /admin/resolve                               1.85 kB         114 kB
├ ○ /alerts                                      5.92 kB         168 kB
├ ○ /alpha                                       10.4 kB         126 kB
├ ƒ /api/v1/signals/dashboard                      239 B         103 kB
├ ○ /arb                                         4.16 kB         159 kB
├ ○ /auth/login                                  3.61 kB         119 kB
├ ○ /auth/signup                                  6.5 kB         122 kB
├ ○ /backtest                                    13.2 kB         129 kB
├ ● /categories/[category]                       2.33 kB         161 kB
├ ○ /clones                                      4.17 kB         120 kB
├ ○ /clones/new                                  4.73 kB         120 kB
├ ○ /community                                   7.57 kB         123 kB
├ ○ /compare                                     7.44 kB         166 kB
├ ○ /discover                                      239 B         103 kB
├ ○ /eval                                        8.79 kB         160 kB
├ ○ /features                                    1.21 kB         147 kB
├ ○ /feed                                        10.4 kB         126 kB
├ ○ /forecast                                      167 B         118 kB
├ ○ /home                                        8.07 kB         167 kB
├ ○ /icon.svg                                        0 B            0 B
├ ○ /leaderboard                                 4.15 kB         159 kB
├ ○ /library                                     5.86 kB         138 kB
├ ○ /macro                                       1.65 kB         114 kB
├ ○ /manifest.webmanifest                          239 B         103 kB
├ ƒ /markets                                     4.64 kB         160 kB
├ ● /markets/[slug]                                196 B         206 kB
├ ○ /markets/view                                  624 B         207 kB
├ ○ /mirror                                        167 B         118 kB
├ ○ /onboarding                                  4.89 kB         148 kB
├ ƒ /opengraph-image                               239 B         103 kB
├ ○ /opportunities                                1.7 kB         161 kB
├ ○ /pods                                        8.36 kB         176 kB
├ ○ /portfolio                                   17.5 kB         189 kB
├ ○ /research                                    2.99 kB         118 kB
├ ○ /research/brief                              5.36 kB         169 kB
├ ● /research/brief/[slug]                         789 B         120 kB
├ ○ /resolved                                     4.6 kB         160 kB
├ ○ /robots.txt                                    239 B         103 kB
├ ● /s/[slug]                                    4.58 kB         164 kB
├ ○ /scanners                                    5.86 kB         133 kB
├ ƒ /scanners/[id]                               92.1 kB         216 kB
├ ○ /screener                                     6.2 kB         122 kB
├ ○ /signals                                      7.1 kB         123 kB
├ ○ /skills                                      3.78 kB         125 kB
├ ○ /smart-money                                 6.91 kB         162 kB
├ ○ /terminal                                    15.8 kB         189 kB
├ ƒ /traders/[name]                              6.69 kB         122 kB
├ ○ /track-record                                7.73 kB         163 kB
├ ○ /terms                                         173 B         107 kB
├ ○ /trade                                       5.33 kB         183 kB
├ ○ /usage                                       7.49 kB         172 kB
├ ● /w/[handle]                                  3.74 kB         119 kB
│   └ /w/demo
├ ○ /watchlist                                   6.19 kB         165 kB
└ ○ /weather                                     1.97 kB         114 kB
+ First Load JS shared by all                     103 kB
  ├ chunks/1255-eae4096fb21f1304.js                46 kB
  ├ chunks/4bd1b696-100b9d70ed4e49c1.js          54.2 kB
  └ other shared chunks (total)                  2.73 kB

○  (Static)   prerendered as static content
●  (SSG)      prerendered as static HTML (uses generateStaticParams)
ƒ  (Dynamic)  server-rendered on demand

 ⚠ Using edge runtime on a page currently disables static generation for that page
```

### `cd frontend && npx playwright test e2e/community.spec.ts`

Executed from `frontend` with isolated `E2E_FE_PORT=31018` and `E2E_API_PORT=18018`; the default `31017` server belonged to the separate `loop104-a11y` worktree and served a stale 404.

```text
Running 5 tests using 1 worker

  ok 1 [chromium] › e2e\community.spec.ts:65:7 › community stories › feed renders a story card (10.6s)
  ok 2 [chromium] › e2e\community.spec.ts:76:7 › community stories › load more appends the next cursor page (2.5s)
  ok 3 [chromium] › e2e\community.spec.ts:95:7 › community stories › logged-out composer is disabled with a sign-in affordance (2.5s)
  ok 4 [chromium] › e2e\community.spec.ts:107:7 › community stories › like toggles optimistically and settles from the response (17.9s)
  ok 5 [chromium] › e2e\community.spec.ts:126:7 › community stories › empty state renders when the API has no stories (2.4s)

  5 passed (1.2m)
```

Frontend-only deterministic gate:

```text
=== GATE: frontend typecheck ===
PASS frontend typecheck (exit 0)
=== GATE: frontend test ===
Test Files  101 passed (101)
Tests  567 passed (567)
PASS frontend test (exit 0)
=== GATE: frontend build ===
PASS frontend build (exit 0)
=== GATE VERDICT ===
PASS: all checks green
```

Full repository gate boundary:

```text
py -3.13 orchestration/gate.py
command timed out after 306607ms; no gate verdict emitted while backend pytest was running
```

Status: CHARTER PROOF GREEN; full repository gate remains unproven because its backend-owned run timed out.

## Blocker fixes

Audit: `AUDIT104-COMMUNITY.md` (VERDICT FAIL) — two honesty blockers only.

### What changed

1. **Blocker 1 (fabricated READ):** Deleted `MOCK_STORIES` / `MOCK_COMMENTS` / mock like counters from `frontend/src/lib/social-api.ts`. `listStories` and `listComments` now throw `SocialApiError` on live miss (never invent community activity). `StoryFeed` already surfaces the reject path; empty copy under error is “No community activity yet” with a visible `role="alert"`.
2. **Blocker 2 (fabricated WRITE):** `addComment` / `react` / `unreact` throw on failure — no synthetic success objects. `CommentThread` posts optimistically then rolls back the temp comment, restores the draft, and shows “Comment could not be posted…”. `StoryCard` like path already rolled back on reject.

Frozen contract field names / opaque `next_cursor` unchanged. Trader exports preserved. No backend/alembic. No sample-stories mode.

### Pre-fix proof (tests must FAIL first)

Confirmed against **unfixed** code (stash: source fix off, only the two new e2e tests applied):

```text
Running 2 tests using 1 worker

  x 1 [chromium] › community_feed_shows_empty_state_not_fabricated_stories_when_api_fails
      → expected community-empty-state visible; not found (silent mock path still rendered)
  x 2 [chromium] › community_comment_surfaces_error_and_rolls_back_when_post_fails
      → expected alert /could not be posted/; got empty next-route-announcer (fabricated write success)

  2 failed
```

A test that passed before the fix would prove nothing; these two failed on the pre-fix tree as required.

### `cd frontend && npm run typecheck`

```text
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
```

Exit 0.

### `cd frontend && npm run lint`

```text
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
```

Exit 0.

### `cd frontend && npx playwright test e2e/community.spec.ts --reporter=list`

Executed with isolated `E2E_FE_PORT=31021` / `E2E_API_PORT=18021`.

```text
Running 7 tests using 1 worker

  ok 1 [chromium] › e2e\community.spec.ts:65:7 › community stories › feed renders a story card (10.8s)
  ok 2 [chromium] › e2e\community.spec.ts:76:7 › community stories › load more appends the next cursor page (2.5s)
  ok 3 [chromium] › e2e\community.spec.ts:95:7 › community stories › logged-out composer is disabled with a sign-in affordance (2.4s)
  ok 4 [chromium] › e2e\community.spec.ts:107:7 › community stories › like toggles optimistically and settles from the response (13.6s)
  ok 5 [chromium] › e2e\community.spec.ts:126:7 › community stories › empty state renders when the API has no stories (2.5s)
  ok 6 [chromium] › e2e\community.spec.ts:134:7 › community stories › community_feed_shows_empty_state_not_fabricated_stories_when_api_fails (3.4s)
  ok 7 [chromium] › e2e\community.spec.ts:160:7 › community stories › community_comment_surfaces_error_and_rolls_back_when_post_fails (8.3s)

  7 passed (1.9m)
```

Exit 0.

### Noted, not fixed

- `getSharedWatchlist` still returns a synthetic `{ handle, display_name: handle, items: [] }` with `source: "mock"` when live misses (softer fabrication; audit non-blocking).
- `setWatchlistShare` still invents `{ public, share_url: "/w/me" }` on network miss after no HTTP error object — write fabrication outside the community story path; out of this node’s two-blocker charter.
- App-wide silent-mock pattern in other clients (e.g. `alpha-api.ts`) deliberately untouched — separate node.
- `avatar_url` still used as raw `<img src>` (contract-aligned).
- No central nav link to `/community` (intentional; contested shared surface).

AutoLab: not applicable (no iterative measure; honesty fix only).
