# Loop V23 — Admin operations backend (roadmap Phase 3 admin)

> Runner: Grok CLI. Worktree E:/polymarket-worktrees/loop23-admin, branch
> loop23/admin. Constitution = goals/loop-v15-backend-massive/GOAL.md rules.
> Orchestrator reviews every commit.

## Ownership
YOURS: backend/app/api/v1/admin_markets.py (EXISTS — read first, extend),
new backend/app/api/v1/admin_users.py + admin_stats.py, services they need,
tests, goals/loop-v23-admin/**. Shared files via SHARED FILE CLAIMS here.
MIGRATION: PRE-ASSIGNED 045 if genuinely needed (prefer none; chain from 044
if V22 landed it, else 043 — CHECK `uv run alembic heads` first and record).
FOREIGN: frontend/**, connectors, social_*, workers wiring, deploy configs.

## Guardrails
EVERY endpoint admin-gated (verify_admin_api_key dependency — the C3 pattern);
PAPER_TRADING_ONLY; order path untouched; destructive admin actions (pause/
cancel market) must write an audit row (reuse/extend existing audit patterns —
READ first); additive API; fixtures-only tests; check gate COUNTS; fresh
verifier per ticket.

## Tickets (continuous; commit feat(loop23): <ticket>)
- A1 Market management: read admin_markets.py first; ensure/complete
  create/edit/pause/unpause/cancel endpoints with validation + audit log +
  tests (resolution stays with external_resolve — do NOT add manual resolve
  beyond what exists).
- A2 User administration: GET /api/v1/admin/users (paginated, search),
  per-user detail (balance, trade count, flags), POST suspend/unsuspend
  (suspended users can't trade — enforce in the paper-order path via the
  EXISTING risk/validation layer, minimal additive check + tests).
- A3 System stats: GET /api/v1/admin/stats — totals (users, markets by
  status, trades 24h/7d, forecasts locked/graded, DB row counts for key
  tables) — single cheap aggregate query set, cached 30s.
- A4 Full gate + verifier + OpenAPI polish. STOP after A4.
