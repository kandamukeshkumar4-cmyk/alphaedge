# Loop V22 — Social layer backend (roadmap Phase 6)

> Runner: ChatGPT/Codex IDE. Worktree E:/polymarket-worktrees/loop22-social,
> branch loop22/social. Constitution = goals/loop-v15-backend-massive/GOAL.md
> rules (guardrails, claims, gate). Orchestrator reviews every commit.

## Ownership
YOURS: new backend/app/api/v1/social.py, new backend/app/services/social_*.py,
their tests, goals/loop-v22-social/**. Shared files (routes.py, db/models.py,
schemas/**, main.py router line) via SHARED FILE CLAIMS in STATE.md, additive
only. MIGRATION: you are PRE-ASSIGNED number 044 (chain from 043_signal_events_created_idx,
ONE head). FOREIGN: frontend/**, connectors, workers wiring, deploy configs.

## Guardrails
PAPER_TRADING_ONLY; order path untouched; public surfaces NEVER leak emails —
reuse the anonymized_username / display_name pattern from analytics_leaderboard;
additive API only; fixtures-only tests; never weaken a test; check gate COUNTS
(piped exit codes lie). Fresh verifier per ticket.

## Tickets (continuous; commit feat(loop22): <ticket>)
- S1 Public trader profiles: GET /api/v1/social/traders/{anon_or_display_name}
  — public stats (win rate, ROI, trade count, member-since; NO email/id leak),
  reusing leaderboard math. 404 for unknown; opt-out flag on user (migration
  044 col users.profile_public default true).
- S2 Follow system: POST/DELETE /api/v1/social/follow/{trader}, GET
  /api/v1/social/following + followers count on profiles (auth; unique
  follower+followee in 044; no self-follow; idempotent).
- S3 Followed-trader activity: GET /api/v1/social/feed — anonymized recent
  trades of traders you follow (reuse B4 activity plumbing; auth).
- S4 Wire-up + polish: OpenAPI tags/summaries (snapshot test will assert),
  rate-limit sanity (mutating endpoints inherit E1 limits — test one), full
  gate + verifier. STOP after S4.
