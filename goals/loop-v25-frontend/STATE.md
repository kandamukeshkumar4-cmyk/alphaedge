# Loop V25 — STATE
| ID | Ticket | Status | Notes |
|----|--------|--------|-------|
| F1 | Trader profile page | DONE | `/traders/[name]` uses the public social profile contract and authenticated follow/unfollow. Frontend gates: typecheck, lint, Vitest 64 files / 377 tests, build green. Initial shared Playwright run had one transient Discover mobile failure; fresh rerun at F3 passed 24, skipped 1. Fresh adversarial verifier: PASS. |
| F2 | Social feed surface | DONE | Following tab uses authenticated GET /api/v1/social/feed and leaderboard rows link to /traders/{name}. Frontend gates: typecheck, lint, Vitest 64 files / 377 tests, build green. Initial shared Playwright run had one transient Discover mobile failure; fresh rerun at F3 passed 24, skipped 1. Fresh adversarial verifier: PASS. |
| F3 | Notification bell | DONE | Real REST notification list, unread badge, mark-one/all-read actions, and `notifications` WS channel are wired. Frontend gates: typecheck, lint, Vitest 65 files / 379 tests, build green. Playwright: 24 passed, 1 skipped. Fresh adversarial verifier: PASS. |
| F4 | Admin panel | TODO | key in memory only |
| F5 | Eval/drift panel | TODO | |

## LOOP LOG

| F1 | 2026-07-14 | DONE | commit `1bb994a`; frontend gates green; later fresh Playwright verifier `24 passed, 1 skipped`; adversarial PASS |
| F2 | 2026-07-14 | DONE | commit `65d5d52`; frontend gates green; later fresh Playwright verifier `24 passed, 1 skipped`; adversarial PASS |
| F3 | 2026-07-14 | DONE | frontend gates green; Playwright `24 passed, 1 skipped`; adversarial PASS |
