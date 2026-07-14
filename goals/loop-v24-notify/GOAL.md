# Loop V24 — Notification center & daily digest (backend)

> Runner: Grok CLI. Worktree E:/polymarket-worktrees/loop24-notify, branch
> loop24/notify. Constitution = goals/loop-v15-backend-massive/GOAL.md rules.

## Ownership
YOURS: new backend/app/api/v1/notifications.py, new backend/app/services/
notification_*.py, new worker module backend/app/workers/daily_digest.py,
tests, goals/loop-v24-notify/**. Shared files via SHARED FILE CLAIMS
(routes.py/db/models.py/schemas/main.py/workers tasks.py), additive only.
MIGRATION: PRE-ASSIGNED 046 — id UNDER 32 CHARS (hard constraint: the column
is varchar(32); two deploys failed on this today), chain from CURRENT head
(check `uv run alembic heads`; 045_admin_cancel_suspend expected).
FOREIGN: frontend/**, connectors, social_*, admin_*, deploy configs.

## Guardrails
PAPER_TRADING_ONLY; order path untouched; in-app ONLY (no email/telegram/push
— E08 decision stands); reuse AlertDispatchService + the `alerts` WS topic,
do not build a parallel alert system; additive API; fixtures-only tests;
check gate COUNTS; fresh verifier per ticket. New worker MUST be wired both
as ARQ registration AND as an in-process flag-gated loop in main.py
(_paced_sleep pattern — prod has no ARQ worker; see forecast_autolock).

## Tickets (continuous; commit feat(loop24): <ticket>)
- N1 Notification model + API: migration 046 (user notifications: type,
  title, body, link, read_at, created_at, index user+created); GET
  /api/v1/notifications (auth, cursor-paginated, unread count), POST
  /api/v1/notifications/{id}/read + /read-all (idempotent).
- N2 Producers: fan existing events into per-user notifications — order
  filled/cancelled (from the B4/A3 event paths), followed-trader trade (if
  V22 social tables exist in your base — check; skip gracefully if not,
  noting it), drift/ops alerts mirrored to admins only. Never raises into
  the producing transaction (E3/B4 pattern).
- N3 Daily digest worker: workers/daily_digest.py — once per user per day
  (idempotent), summarize: portfolio change, positions resolved, top market
  moves among watchlist/followed; store AS a notification (type=digest).
  Wire ARQ + in-process loop (flag default ON, long paced interval).
- N4 Gate + OpenAPI polish + WS: publish new-notification events on the
  existing multiplex hub as a `notifications` channel (E03 pattern). STOP.
