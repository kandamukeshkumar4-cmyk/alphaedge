# Loop V28 — STATE
| ID | Ticket | Status | Notes |
|----|--------|--------|-------|
| G1 | Social journeys | DONE | social.spec.ts: follow/Following/stats/unfollow/opt-out; BUG-V28-01 fixme |
| G2 | Notification journeys | TODO | |
| G3 | Admin + eval journeys | TODO | |
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

## LOOP LOG
| loop | date | result | proof |
|------|------|--------|-------|
| G1 | 2026-07-14 | DONE | typecheck exit 0; playwright 25 passed / 2 skipped (3.9m) |

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
