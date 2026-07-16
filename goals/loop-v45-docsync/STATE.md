# loop-v45-docsync — STATE

## Tickets

| Ticket | Status | Commit | Notes |
|--------|--------|--------|-------|
| W1 Diff + document missing OpenAPI surfaces | DONE | `53ed5f7` | Snapshot = 154 path keys; priority surfaces tabled |
| W2 User-guide additions | DONE | `78563ea` | bell, profiles, /eval, resolved-count source |
| W3 Ops runbook additions | DONE | (this commit) | loops, autolock funnel, visreg, CI |

## W1 — OpenAPI vs `docs/api.md` gap list

**Sources:** `backend/tests/fixtures/openapi_snapshot.json` (flat path→methods map, **154** keys) vs path strings present in `docs/api.md` before W1 edits.

### Priority missing surfaces (GOAL named)

| Surface | Paths in snapshot | Pre-W1 in api.md? |
|---------|-------------------|-------------------|
| Social | `GET /api/v1/social/traders/{trader}`, `POST/DELETE /api/v1/social/follow/{trader}`, `GET /api/v1/social/following`, `GET /api/v1/social/feed` | **Missing** |
| Notifications | `GET /api/v1/notifications`, `POST …/read-all`, `POST …/{id}/read` | **Missing** |
| Admin suite (users/stats/lifecycle) | `GET /api/v1/admin/stats`, `GET /api/v1/admin/users`, `GET …/users/{id}`, `POST …/suspend`, `POST …/unsuspend`, `POST …/markets/{slug}/pause\|unpause\|cancel`, `POST …/external-markets/{id}/resolve` | **Partial** (jobs/markets list/resolve/observability only) |
| Eval / drift | `GET /api/v1/eval/drift` (public) **and** `GET /api/v1/admin/observability/drift` | **Incorrect** — api.md claimed no public eval/drift |
| System sources | `GET /api/v1/system/sources` | Present (admin) |
| Models | `GET /api/v1/models`, `POST …/{version_id}/activate`, `POST …/rollback` | **Missing** |

### Additional snapshot paths not individually tabled (pre-W1)

Summarized only under “Other public / product surfaces” or omitted:

- Forecast mirror detail: `/api/v1/forecasters/*`, `/api/v1/forecasts`, `/api/v1/backfill/markets`, `/api/v1/telemetry/mirror/events`, `/api/v1/markets/external/resolve-url`
- Clones subpaths: leaderboard, nodes, `{clone_id}` CRUD/run/runs/scorecard/versions
- Backtest detail: `/api/v1/backtest/runs`, `…/runs/{run_id}`, `…/summary`

W1 documents **priority** surfaces with auth + file citations; forecast/clones/backtest remain summary rows (already flagged as product surfaces) unless expanded later.

### Auth summary (code-verified)

| Path family | Auth | Code |
|-------------|------|------|
| social traders GET | Public | `backend/app/api/v1/social.py` |
| social follow/following/feed | JWT `get_current_user` | same |
| notifications * | JWT | `backend/app/api/v1/notifications.py` |
| models * | Admin `verify_admin_api_key` | `backend/app/api/v1/models.py` |
| admin users/stats/markets lifecycle | Admin | `admin_users.py`, `admin_stats.py`, `admin_markets.py` |
| eval/* including `/drift` | Public (no admin) | `backend/app/api/v1/eval_routes.py` |
| system/sources | Admin (router deps) | `backend/app/api/v1/sports.py` `sources_router` |
| system/resolved-count | Public; returns `source` + `forecast_scored_count` | `backend/app/api/v1/system.py` |

## W3 grep-verification (paste)

```
code _ALL_LOOPS count 20; missing []
DOC=True all 20 loop names (price_feed … data_retention)
DOC=True bridge/autolock/digest/ops_alerts/jobrun_retention/data_retention workers/*
DOC=True paper_orders_fallback, forecast_scores funnel honesty
DOC=True visreg.spec.ts, stable-shot.ts, --project=visreg, --update-snapshots, testIgnore
DOC=True ci-backend.yml, ci-frontend.yml, ci-e2e.yml, demo-uptime.yml
FILE=True all six worker modules + visreg + three CI ymls
```

## LOOP VERDICT

**W1–W3 DONE.** Docs only (`docs/**`, `goals/loop-v45-docsync/**`). No app code,
no secrets, no push/merge.

## W2 grep-verification (paste)

```
DOC=True  NotificationBell, /api/v1/notifications, notifications-api.ts
DOC=True  /traders/[name], social traders/follow/following/feed, /feed?view=following
DOC=True  /eval, /api/v1/eval/aggregates, /api/v1/eval/drift, ModelAbCard
DOC=True  /api/v1/system/resolved-count, forecast_scores, paper_orders_fallback,
          forecast_scored_count, resolved_outcomes_breakdown
FILE=True NotificationBell.tsx traders/[name]/page.tsx eval/page.tsx ModelAbCard.tsx
          ab_harness.py system.py
```

## W1 grep-verification (paste)

```
SNAP=True DOC=True  /api/v1/social/traders/{trader}
SNAP=True DOC=True  /api/v1/social/follow/{trader}
SNAP=True DOC=True  /api/v1/social/following
SNAP=True DOC=True  /api/v1/social/feed
SNAP=True DOC=True  /api/v1/notifications
SNAP=True DOC=True  /api/v1/notifications/read-all
SNAP=True DOC=True  /api/v1/notifications/{notification_id}/read
SNAP=True DOC=True  /api/v1/eval/drift
SNAP=True DOC=True  /api/v1/models
SNAP=True DOC=True  /api/v1/models/rollback
SNAP=True DOC=True  /api/v1/models/{version_id}/activate
SNAP=True DOC=True  /api/v1/admin/stats
SNAP=True DOC=True  /api/v1/admin/users
SNAP=True DOC=True  /api/v1/admin/users/{user_id}
SNAP=True DOC=True  /api/v1/admin/users/{user_id}/suspend
SNAP=True DOC=True  /api/v1/admin/users/{user_id}/unsuspend
SNAP=True DOC=True  /api/v1/admin/markets/{slug}/pause
SNAP=True DOC=True  /api/v1/admin/markets/{slug}/unpause
SNAP=True DOC=True  /api/v1/admin/markets/{slug}/cancel
SNAP=True DOC=True  /api/v1/admin/external-markets/{external_market_id}/resolve
SNAP=True DOC=True  /api/v1/system/sources
SNAP=True DOC=True  /api/v1/system/resolved-count
file cites: social.py notifications.py eval_routes.py models.py admin_* system.py sports.py
wrong claim "no public eval/drift" removed = True
non-priority still summary-only: backtest runs/summary, clones subpaths, forecasters/me/*
```

## LOOP LOG

| when | ticket | action |
|------|--------|--------|
| start | — | branch `loop45/docsync` clean; GOAL binding read |
| W1 | DONE | docs/api.md + STATE gap list; 22 priority paths SNAP+DOC |
| W2 | DONE | user-guide: NotificationBell, social follow, /eval, resolved-count source |
| W3 | DONE | operations: _ALL_LOOPS, funnel, visreg, CI workflows |
