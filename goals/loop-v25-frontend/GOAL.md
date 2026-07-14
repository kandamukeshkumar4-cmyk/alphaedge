# Loop V25 — Frontend surfacing of wave-1/2 backend features

> Runner: ChatGPT/Codex IDE, AFTER loop V22 completes. Worktree
> E:/polymarket-worktrees/loop25-frontend, branch loop25/frontend.

## Ownership
YOURS: frontend/src/** EXCEPT chart components (OrderbookDepthChart.tsx and
frontend/src/lib/chart-colors.* are owned by a parallel fix session — do not
touch), plus goals/loop-v25-frontend/**. FOREIGN: backend/**, e2e/** (QA
suite owns it; new pages must still pass it), deploy configs.

## Guardrails
Design rules in frontend/.claude/CLAUDE.md; text-bg on accent (V9 contrast
rule — never white-on-mint); honest empty states with "where to click next";
gate per ticket: npm run typecheck && npm run lint && npm test && npm run
build (check counts) + npx playwright test must stay green (24 passed);
fresh verifier per ticket.

## Tickets (continuous; commit feat(loop25): <ticket>)
- F1 Trader profile page: /traders/[name] consuming GET /api/v1/social/
  traders/{name} + follow/unfollow buttons (auth-gated), followers count.
- F2 Social feed surface: followed-trader activity on /feed (or a "Following"
  tab) from /api/v1/social/feed; link Top Traders/leaderboard rows to
  profiles.
- F3 Notification bell: real notification center consuming /api/v1/
  notifications (list, unread badge, mark-read) + `notifications` WS channel
  — replace any placeholder bell. If loop V24 endpoints are not in your base
  yet, build against the documented API shape with mocks OFF by default and
  mark BLOCKED-ON-MERGE honestly.
- F4 Admin panel page: /admin (client-side gated on admin key entry, key
  held in memory only — NEVER localStorage) surfacing admin/stats, market
  pause/cancel, user suspend from the V23 endpoints.
- F5 Eval/drift panel: /eval or a Model page section charting GET /api/v1/
  eval/drift + model registry list. Full gates + e2e green. STOP.
