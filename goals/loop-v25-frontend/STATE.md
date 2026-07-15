# Loop V25 — STATE
| ID | Ticket | Status | Notes |
|----|--------|--------|-------|
| F1 | Trader profile page | BLOCKED | Frontend gates pass: typecheck, lint, build; Vitest 64 files / 377 tests. Required Playwright gate is not green: 23 passed, 1 skipped, 1 failed at existing e2e/mobile.spec.ts:105 because the Discover "Trending" pill is 30px high (expected >=32px). Fresh adversarial verifier: F1 diff PASS; ticket BLOCKED on this unrelated pre-existing gate failure. |
| F2 | Social feed surface | TODO | |
| F3 | Notification bell | TODO | may be BLOCKED-ON-MERGE until V24 lands |
| F4 | Admin panel | TODO | key in memory only |
| F5 | Eval/drift panel | TODO | |

## LOOP LOG
