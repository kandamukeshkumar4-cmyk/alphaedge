# Loop V22 — STATE
| ID | Ticket | Status | Notes |
|----|--------|--------|-------|
| S1 | Public trader profiles (+044) | DONE | 2026-07-14 pre-read: reused `analytics_leaderboard.anonymized_username` and settlement math; added `GET /api/v1/social/traders/{anon_or_display_name}`, `users.profile_public` default true, `Follow` constraints for S2, and migration `044_social` chained from `043_signal_events_created_idx` (one head). Public response has no email/id fields; opt-out/unknown/ambiguous profiles return 404; fixtures-only tests cover win rate, ROI, trade count, member-since, display names, and privacy. Backend gate tail: `1509 passed, 28 skipped in 331.43s`; Ruff: `All checks passed!`. Orchestration gate: backend pytest PASS (`1509 passed, 28 skipped`), backend Ruff PASS; overall gate blocked only by untouched frontend environment (`tsc`, `vitest`, and `next` not installed), so no frontend files were changed. Fresh adversarial verifier: PASS — `1509 passed, 28 skipped in 395.70s`; Ruff `All checks passed!`; `044_social (head)`. |
| S2 | Follow system | TODO | |
| S3 | Followed-trader feed | TODO | |
| S4 | Wire-up + polish | TODO | |

## SHARED FILE CLAIMS
| File | Ticket | Status |
|---|---|---|
| `backend/app/db/models.py` | S1 | RELEASED — additive `User.profile_public` and `Follow` model only |
| `backend/app/main.py` | S1 | RELEASED — additive social router import/include only |

## MIGRATION CLAIMS
| Revision | Ticket | Status |
|---|---|---|
| `044_social` | S1/S2 | RELEASED — chains from `043_signal_events_created_idx`; one head |

## LOOP LOG
