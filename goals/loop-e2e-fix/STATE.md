# Loop E2E-FIX — repair pre-existing local-stack Playwright failures (2026-07-30)

> Orchestrator: Claude (Fable 5, resumed session). Executors: parallel
> diagnosis agents (one per failing spec) → implementer → verifier.
> Branch: `claude/missing-edge-thread-yqbqoc` (PR #58).

## Context

CI job "Local-stack Playwright" fails the SAME 5 specs deterministically on
the base branch (`codex/alphaedge-base`) and on every commit of PR #58
(whose diff is docs + static metadata routes + a workflow trigger — none of
these surfaces). The failures predate the PR and came out of frontend waves
104–117. Failure signatures are element-visibility timeouts.

## Tickets

| # | Ticket | Spec | Status |
|---|--------|------|--------|
| E1 | admin-eval: admin key via UI not in storage; stats; pause/unpause | e2e/admin-eval.spec.ts:67 | TODO |
| E2 | alpha: /alpha renders factor ledger + validated-factor report | e2e/alpha.spec.ts:19 | TODO |
| E3 | coachmarks: Getting started on first visit, persists dismiss | e2e/coachmarks.spec.ts:13 | TODO |
| E4 | loading-states: notification bell loading then honest state | e2e/loading-states.spec.ts:63 | TODO |
| E5 | marketplace: /library shows Trending + Featured above tabs | e2e/marketplace.spec.ts:86 | TODO |
| E6 | search: two header-search journeys | e2e/search.spec.ts:82, :125 | TODO |
| E7 | terminal: session steps/scoreboard + canvas node graph | e2e/terminal.spec.ts:15, :36 | TODO |
| E8 | v79-visual: A7 shots | e2e/v79-visual.spec.ts:10 | TODO |

> 2026-07-30 correction: the CI log truncation hid 5 more failing tests —
> the job fails 10 unique tests, not 5. E6–E8 added.

## Method

1. Per spec: diagnosis agent reads the spec's selectors/expectations and the
   current components/pages it exercises; identifies the drift (renamed
   testid, moved section, changed copy, removed element) and whether the fix
   belongs in the SPEC (UI intentionally changed in waves 104–117) or in the
   UI (regression). Evidence required — file:line for both sides.
2. Implementer applies the smallest fix per ticket. Guardrails: never weaken
   an assertion to pass; if the UI regressed, fix the UI, not the test.
3. Gate: `npm run typecheck && npm run lint && npx vitest run && npm run build`
   green locally. Full Playwright verification happens in CI (local container
   has no Postgres service).

## Guardrails

PAPER_TRADING_ONLY untouched; no order-path changes; no fabricated data;
scope = frontend specs/components implicated by E1–E5 only.

## OUTCOME (2026-07-30)

CI on `3b2fe76`: Backend ✓, Frontend ✓, **Local-stack Playwright ✓** — all
10 pre-existing failures repaired across 3 iterations. AutoLab:
baseline=10 failed e2e tests on base | benchmark=CI Playwright failure
count | iterations=3 (10 → 6 → 6 → 0) | budget=3/3 | outcome=improved.

## LOOP LOG

| iter | date | ticket | result | proof |
|------|------|--------|--------|-------|
| 1 | 2026-07-30 | E1 | DONE (UI regression) | /eval ensemble catch() set the spec-rejected `unavailable` state on 404 while the intended `notRun` fallback object sat dead — wired the catch to `setAutolab(notRun)`, removed the unreachable `ensemble-unavailable` branch. Typecheck + 581 vitest green. |
| 1 | 2026-07-30 | E2 | DONE (spec fix) | Live local stack returns honest-empty alpha factors (intentional, commit 1775f8a) — spec now forces the documented mock path via route 404 intercept; all 7-factor assertions kept at full strength. |
| 1 | 2026-07-30 | E3 | DONE (spec fix) | Loop-104 OnboardingTour (z-100) covered CoachMarks (z-40); seeded `ae_onboarded_v1` like portfolio-analytics.spec already does. |
| 1 | 2026-07-30 | E4 | DONE (UI + spec) | V90 NotificationCenter skeleton was aria-hidden with no accessible text — added sr-only "Loading notifications…" + `notifications-loading` testid; spec asserts testid and the current intentional empty copy. |
| 3 | 2026-07-30 | E3 | DONE iter2 (spec determinism) | CI on 2e704b4: card shows and dismisses, but reappeared after reload — addInitScript reruns on EVERY navigation, so the seed re-removed the seen-flag post-dismiss. Now clears the flag only on first load (sessionStorage guard). |
| 3 | 2026-07-30 | E6 | DONE (spec fix) | Both palette tests verify the PAPER mock fallback, but the local-stack backend is UP: "Lakers" returned live rows (different title) and "Bitcoin" honestly returned zero live rows. Tests now abort `/api/v1/search` to force the documented mock path; all assertions kept. |
| 3 | 2026-07-30 | E7+E8 | DONE (spec fix) | Terminal smokes + A7 shots verify the seeded MOCK session, but the live terminal API now requires auth → honest signed-out state, no step cards. beforeEach aborts `/api/v1/terminal/**` to force the offline mock path (fetch error → mock, verified in terminal-api.ts tryLiveJson). |
| 2 | 2026-07-30 | E4 | DONE (lib honesty fix) | CI on f4fcede showed E4's loading testid passed but the empty state never rendered: `notifications-api.list()` replaced a VALID empty live page with seeded mock items (fabricated data). Empty live page is now authoritative (`source: live`, honest empty); mock fallback only for absent/error/malformed API. 6/6 lib unit tests + 581 vitest green. CI f4fcede also confirms E1/E2/E3/E5 fixed (10 failed → 6 failed). |
| 1 | 2026-07-30 | E5 | DONE (spec fix) | Loop-104 intentionally replaced the /library marketplace spotlight with the research archive (coverage lives in library.spec.ts); obsolete test removed. |
