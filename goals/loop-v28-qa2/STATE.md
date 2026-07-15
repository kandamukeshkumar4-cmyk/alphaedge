# Loop V28 — STATE
| ID | Ticket | Status | Notes |
|----|--------|--------|-------|
| G1 | Social journeys | DONE | social.spec.ts: follow/Following/stats/unfollow/opt-out; BUG-V28-01 fixme |
| G2 | Notification journeys | DONE | notifications.spec.ts: unread after follow+trade; mark-all; mark-one; badge clears |
| G3 | Admin + eval journeys | DONE | admin-eval.spec.ts: key not in storage; stats; pause/unpause; /eval drift empty; BUG-V28-02 |
| G4 | Watching-count flaky fix | TODO | |

## BUG REPORTS

### BUG-V28-01 · social feed trader label ignores display_name
- **Surface:** `/feed?view=following` (FollowedTraderFeed) + GET `/api/v1/social/feed`
- **Symptom:** After setting `display_name` via PATCH `/auth/me`, profile `/traders/{display_name}` resolves correctly, but Following feed cards label the trader as `Trader-<6hex>` only.
- **Root (read-only):** `social_feed.list_followed_trader_activity` → `trade_activity_payload` → `public_trader_label(user_id)` which calls `anonymized_username(user_id)` without `display_name`.
- **Repro:** G1 journey — signup B, set display_name, paper buy, A follows B, open Following tab.
- **Impact:** UX inconsistency; links still work via Trader-hash if that label matches profile fallback when display_name unset, but with display_name set the feed link `/traders/Trader-xxx` may 404 while `/traders/{display_name}` works.
- **Owner:** backend social_feed / analytics_activity (not loop28 — tests only).
- **Journey handling:** main G1 asserts slug + non-empty trader label; `test.fixme` id BUG-V28-01 for display_name equality.

### BUG-V28-02 · TradingView logo nested-interactive inside role=img chart
- **Surface:** market detail price history (`role="img"` chart shell) + lightweight-charts vendor chrome
- **Symptom:** axe `nested-interactive` (serious) when `#tv-attr-logo` (TradingView attribution link) is focusable inside the chart container marked `role="img"`.
- **Root (read-only):** vendor LWC injects attribution anchor; our shell uses role=img for a11y chart region → nested interactive.
- **Repro:** a11y market detail after chart fully mounts (timing-sensitive; flaked G3 full suite).
- **Impact:** screen-reader / keyboard focus inside img role; not a functional trade bug.
- **Owner:** frontend chart wrapper (not loop28 — tests only).
- **Journey handling:** filtered from axe fail set with BUG id; `test.fixme` tracks product fix. Other serious/critical still fail.

## LOOP LOG
| loop | date | result | proof |
|------|------|--------|-------|
| G1 | 2026-07-14 | DONE | typecheck exit 0; playwright 25 passed / 2 skipped (3.9m) |
| G2 | 2026-07-15 | DONE | typecheck exit 0; playwright 26 passed / 2 skipped (5.3m) |
| G3 | 2026-07-15 | DONE | typecheck exit 0; playwright 27 passed / 3 skipped (3.8m) |

## GATE EVIDENCE — G1
```
npm run typecheck → exit 0
npx playwright test → exit 0
  25 passed
  2 skipped  (legacy app.spec + BUG-V28-01 fixme)
  (3.9m)
```

## VERIFIER VERDICT — G1 (fresh adversarial)
- **PASS.** Ownership: only `frontend/e2e/**` + STATE.md; no app code edits.
- **PASS.** Local stack only (start-local-stack.mjs, ports 18017/31017); never prod.
- **PASS.** Journey covers: A+B UI signup, B paper trade, A follows from profile, Following tab activity, profile stats tiles, unfollow → empty Following, opt-out via SQLite (no UI/API) → Profile not available.
- **PASS.** Suite ends green with counts; new BUG-V28-01 documented + fixme, not silently filtered.
- **PASS.** Opt-out harness uses e2e SQLite helper (GOAL: API-set if no UI); no `profile_public` user API exists — residual product gap, not a test weaken.
- Residual risk: feed label bug may 404 trader links from Following when display_name is set (BUG-V28-01).

### ORCHESTRATOR REVIEW · G1 · 18e8627 · verdict: PASS
Journey coverage right-shaped; BUG-V28-01 filed correctly. Continue G2-G4.

## GATE EVIDENCE — G2
```
npm run typecheck → exit 0
npx playwright test → exit 0
  26 passed
  2 skipped  (legacy app.spec + BUG-V28-01 fixme)
  (5.3m)
```

## VERIFIER VERDICT — G2 (fresh adversarial)
- **PASS.** Ownership: only `frontend/e2e/notifications.spec.ts` + STATE.md; no app code.
- **PASS.** Journey: A follows B, B paper-trades → A's bell aria-label shows N unread; center lists followed_trade + canonical slug.
- **PASS.** Mark all read → unread 0 and "Mark all read" control gone; second trade → mark-one via item click → badge clears to aria-label "Notifications".
- **PASS.** WS live bump not asserted (honest poll via remount fetch after navigation); noted in spec header.
- **PASS.** Suite ends green with counts; zero console errors on A/B journeys.
- Residual: mark-one uses link navigation (item has /markets/ link); relies on POST /read completing before remount fetch.

## GATE EVIDENCE — G3
```
npm run typecheck → exit 0
npx playwright test → exit 0
  27 passed
  3 skipped  (legacy app.spec + BUG-V28-01 + BUG-V28-02 fixmes)
  (3.8m)
```

## VERIFIER VERDICT — G3 (fresh adversarial)
- **PASS.** Ownership: `frontend/e2e/admin-eval.spec.ts`, a11y known-bug filter, STATE.md; no app code.
- **PASS.** Dev key `dev-admin-key` entered via UI (#admin-api-key + Save Key); assert not in localStorage/sessionStorage after entry and after pause/unpause.
- **PASS.** System stats tiles render with numeric values; pause → locked → unpause → open on nba-2025-01-15-lal-bos.
- **PASS.** /eval Proof dashboard + drift panel; honest empty (No drift snapshots yet / unavailable) accepted; ensemble settles to not-measured or measured.
- **PASS.** assertNoConsoleErrors on /admin and /eval.
- **PASS.** BUG-V28-02 filed + narrow filter (tv-attr-logo/tradingview nested-interactive only) + fixme; suite green.
- Residual: pause leaves market locked if unpause fails mid-run (round-trip asserts recovery).

### ORCHESTRATOR REVIEW · G2 · 4bffa06 · verdict: PASS
Continue G3 → G4.
