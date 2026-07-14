# Loop V16 — Data Freshness & Liveliness (end-user-visible fixes)

> Runner: ChatGPT/Codex IDE, LOCAL, in worktree `E:/polymarket-worktrees/loop16-fresh`
> on branch `loop16/freshness`. One ticket per iteration. This file is the
> constitution; STATE.md is the memory — update it EVERY iteration.

## WHY (grounded in a real end-user test, 2026-07-13)

The user tested prod (https://alphaedge-frontend-three.vercel.app on the new
Railway backend) and reported "nothing is working, no new data, old data
processed again and again." Verified symptoms from screenshots:

1. Discover "Trending Markets" is dominated by DEAD markets — eliminated
   WC teams at 0% (Egypt/Morocco/USA/Norway/Belgium "Will X win the 2026 FIFA
   World Cup?" — the tournament is in its final week, these are honestly ~0¢)
   ranked purely by lifetime volume. Real data, WRONG surfacing: a trending
   list full of 0% flatlines reads as broken/stale.
2. "Live Signals" left rail shows 5+ IDENTICAL rows "SHORT POLY
   delta:price_jump —" with em-dash values — repeated/degenerate signal
   rendering, no market name, no magnitude, no timestamp.
3. Signal feed cards show "NEEDS MORE HISTORY", NET EDGE "—", SAMPLE "—",
   "Not enough resolved bets to score this yet (under 30)" — honest but the
   root cause is fixable: resolved_count=1 because model forecasts are never
   auto-locked pre-close (loop-v14's documented F04 follow-up was never built),
   so nothing ever grades and every intelligence surface stays empty forever.
4. Bottom ticker replays the same old trades/briefs (e.g. July-7 "Elon Musk
   Of Tweets" entries) — looks like a loop of stale events.
5. Top Traders / Paper P&L are $0/empty — honest (no graded trades yet), NOT
   a bug; leave the empty states alone but they compound the "dead app" feel.

## PRIME DIRECTIVE: DIAGNOSE BEFORE FIXING

For every ticket, FIRST verify the hypothesis against live evidence (prod API
reads are fine: https://alphaedge-api-production-b9db.up.railway.app/api/v1/*,
plus local stack + tests). Some "stale-looking" data is CORRECT (eliminated
teams at 0%). Never fabricate liveliness: no fake movement, no invented
volumes, no seeding fake trades, no lowering the 30-resolved-bets scoring
threshold. The fix is honest surfacing + honest pipeline completion.

## Parallel-safety (other loops are running RIGHT NOW)

- FOREIGN — NEVER EDIT: `backend/app/data/connectors/**` and
  `backend/app/api/v1/sports.py` (Workstream C, active in loop15-c);
  `backend/app/observability/**`, `backend/app/core/ratelimit*`,
  `backend/app/api/v1/health.py`, `backend/app/api/v1/observability.py`
  (Workstream E, active in loop15-e); deploy configs (railway.toml/json,
  Dockerfile, workflows); other goals/ folders.
- YOURS: `frontend/**` (no other loop owns frontend now), plus backend
  surfaces listed per ticket below.
- SHARED FILES (`backend/app/api/v1/routes.py`, `ws.py`, `db/models.py`,
  `schemas/**`, `workers/tasks.py`): claim in STATE.md "SHARED FILE CLAIMS"
  BEFORE editing (check goals/loop-v15-backend-massive/STATE.md claims too),
  additive region-scoped edits only, release on commit.
- Alembic: 038/039/040 landed; claim 041+ in STATE.md before writing one
  (prefer none).
- Never push, never merge, never deploy. Commit to `loop16/freshness` only;
  the orchestrator (Claude main thread) reviews every commit, merges, deploys.

## Hard guardrails (violating any = failed iteration, revert)

PAPER_TRADING_ONLY=true; order path RiskService→OrderIntent→OrderBookService
untouched; additive API only; tests use fixtures (no live network in tests);
never weaken a test; never game a metric; preserve the scoring leakage gate
(never score forecasts locked at/after resolved_at; never backfill post-hoc
forecasts — the count climbs FORWARD in time, that is correct).

## GATE (per ticket, paste tail in STATE.md)

- Backend (from backend/): `ADMIN_API_KEY=dev-admin-key uv run --extra dev
  pytest -q -p no:cacheprovider --basetemp=<scratch>` + `uv run --extra dev
  ruff check app tests`.
- Frontend (from frontend/): `npm run typecheck && npm run lint && npm test
  && npm run build` (required for any ticket touching frontend/**).
- Fresh-context verifier REQUIRED before DONE on every ticket.

## TICKETS (priority order — user-visible impact first)

- **V1 — Trending that actually trends**: Discover/home "Trending Markets"
  and the main grid must rank by RECENT activity (24h volume delta or recent
  price movement or close_at proximity), not lifetime volume; exclude markets
  with price ≤1¢ or ≥99¢ from "Trending" (they're decided — show them under a
  "Longshots/Decided" affordance instead, honestly labeled, e.g. "eliminated").
  Backend: extend the markets listing/home endpoint with the needed sort field
  (additive query param, e.g. sort=active) — read what the frontend calls
  first. Frontend: Discover rail + Trending tab consume it. Evidence: before/
  after JSON of the top-6 trending from prod-shape data.
- **V2 — Live Signals rail renders real signals**: fix the "POLY
  delta:price_jump —" rows: show market title, direction, magnitude (bps or
  ¢), relative time; DEDUPE identical signals per market within a window
  (backend dedupe in the feed/signals query preferred over frontend hiding —
  find why 5 identical rows exist: likely the same event re-emitted or the
  same row rendered 5x). If the payload lacks the fields, fix the emitter
  (signals pipeline persist) additively.
- **V3 — Ticker freshness**: bottom ticker + activity feeds must order by
  created_at DESC, dedupe repeats, and show item age; drop items older than
  a configurable window (default 48h) from the LIVE ticker. If the feed is
  genuinely quiet, show fewer items honestly instead of looping old ones.
- **V4 — F04 auto-lock forecasts (the pipeline completion)**: implement
  loop-v14's documented follow-up: a config-flagged (default ON) bounded
  worker task that locks a model forecast (existing
  `ForecastService.lock_forecast`) for OPEN external markets approaching
  close that lack a LIVE ForecastLog — so genuine pre-close predictions exist
  and `resolved_count` climbs as external_resolve settles them. New module
  `backend/app/workers/forecast_autolock.py` + minimal tasks.py append
  (claim it). Tests: eligible market gets a LIVE lock; already-locked and
  already-closed are skipped; batch bound respected. This unblocks Edge/track
  record/leaderboard grading FOREVER — highest long-term value ticket.
- **V5 — Decided/closed market hygiene**: markets past close_at or at 0/100
  must not carry the green "LIVE" chip; label them "Closed"/"Decided"
  (frontend) and exclude them from "open" counts where dishonest. Backend:
  read-only; reuse existing status fields — if status is wrong in data,
  report it in STATE.md, don't hack the UI.
- **V6 — [LIVE] end-user re-test proof**: local stack (or prod READ-ONLY):
  screenshot/DOM evidence that (a) Trending shows moving markets, (b) signals
  rail shows named deduped signals, (c) ticker shows fresh timestamped items,
  (d) autolock heartbeats and creates LIVE ForecastLogs on eligible markets
  (local stack for this part). Paste into STATE.md.

## Iteration protocol

1. `git status` — confirm worktree/branch. 2. Mark ticket IN-PROGRESS in
STATE.md. 3. DIAGNOSE: reproduce with evidence (prod API JSON / local stack /
failing test) and write 3 lines (root cause / fix plan / files). 4. Smallest
safe fix + tests. 5. Gate green. 6. Fresh verifier, verdict in Notes.
7. Update STATE.md + commit `feat(loop16): <ticket> ...`. One ticket per
iteration. 3 consecutive no-DONE iterations → stop, post-mortem in STATE.md.
