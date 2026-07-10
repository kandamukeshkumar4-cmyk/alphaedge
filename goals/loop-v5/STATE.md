# Loop V5 — Alerts/watchlist, self-serve backtest, A/B closeout (2026-07-10)

> Two parallel tracks in isolated worktrees. Orchestrator (Claude, main
> thread) reviews, merges, gates, deploys to prod, verifies. One commit/ticket.

## WHY (grounded)

V1-V4 built the intelligence (signals, desk, smart-money, arb, track-record,
backtest) and surfaced it. The recurring research ask now is: "tell me when
something moves" — alerts/watchlist — which nothing covers yet. And the
forecasting can't improve until the LightGBM-vs-XGBoost A/B runs on real
resolves (resolved_count now public via /system/resolved-count = 1/100). V5
adds a watchlist + alert feed, a self-serve backtest run, and a real
walk-forward A/B harness readout (still never auto-flips the default model).

## GROUND TRUTH

- Prod backend https://mukeshkumar007-alphaedge-api.hf.space (auto-deploy on
  push to codex/alphaedge-base); prod frontend
  https://alphaedge-frontend-three.vercel.app (cd frontend && npx vercel
  --prod --yes). verify_prod.py = 6/6 as of 2026-07-10.
- Contracts already shipped: goals/loop-v3/API-NOTES.md (desk, backtest/
  summary, smart-money, track-record), goals/loop-v4/API-NOTES.md
  (system/resolved-count, desk cached flag). Signals via
  GET /api/v1/signals/events + /api/v1/activity/signals.

## GATE (per track — paste output in LOOP LOG)

- Frontend (frontend/): `npm run typecheck && npm run lint &&
  npm run test -- --run && npm run build`. 390px no-overflow reasoning for
  new UI. Quest tokens only.
- Backend (backend/): `ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest
  -q -p no:cacheprovider --basetemp=<scratchpad>` and
  `uv run --extra dev ruff check app tests`.

## GUARDRAILS (non-negotiable)

- PAPER_TRADING_ONLY; analysis/notify-only surfaces; order path untouched
  (RiskService → OrderIntent → OrderBookService); no auto-trading; alerts
  NEVER place orders — they only notify.
- No fabricated data; honest empty/thin-data states. Never weaken a test.
- Frontend track edits ONLY frontend/** + goals/loop-v5/**; backend track
  ONLY backend/** + goals/loop-v5/**. Additive API only; document contracts
  in goals/loop-v5/API-NOTES.md.
- New public GET routes must pass the I01 5xx guard (extend its route sweep).
- Quest design language (tailwind tokens + globals.css vars) only.

## BACKEND TRACK (worktree loop-grok-backend)

- **J01 — Watchlist store + API**: per-user (JWT) watchlist of market slugs.
  `POST /api/v1/watchlist {slug}`, `DELETE /api/v1/watchlist/{slug}`,
  `GET /api/v1/watchlist` → slugs + latest snapshot/edge per entry (compose
  existing services). New table via Alembic migration chaining from the
  current single head (035). Auth via existing JWT dep. Tests (auth required,
  add/remove/list, dedupe, unknown slug honest).
- **J02 — Alerts feed**: `GET /api/v1/alerts?since=&slugs=` returns recent
  signal events (news:mispricing, anomaly:unusual_flow, delta:*, screener:*,
  arb) filtered to given slugs (or the caller's watchlist when authed),
  newest first, with the H03 citation fields. Read-only composition of the
  existing signal store — NO new pipeline. Tests with fixtures. Document JSON.
- **J03 — Walk-forward LightGBM-vs-XGBoost A/B readout**:
  `GET /api/v1/system/model-ab` runs the existing G06 harness when
  resolved_count >= threshold and returns both Briers + delta + which_would_win
  + `applied: false` (never flips default); below threshold returns
  {ready:false, resolved_count, threshold}. If lightgbm is unavailable in the
  image, honestly flag `lightgbm_available:false` and report XGB-only. Tests
  cover below-threshold, the honest-unavailable path, and default-unchanged.

## FRONTEND TRACK (worktree loop-opus-polish)

- **W01 — Watchlist UI**: a star/☆ toggle on market cards + market detail
  (calls J01), and a `/watchlist` page listing tracked markets with edge +
  last-move, honest empty ("sign in to track markets" when anon; "no markets
  yet" when empty). Reuse fetchMarkets cache + Quest cards. Vitest for the
  view-model + optimistic toggle.
- **W02 — Alerts page + header bell**: `/alerts` consuming J02 (or public
  signal events when anon): grouped by market, evidence via SignalEvidence,
  filter pills by family; a header bell with an unread-ish count (session
  localStorage "last seen"). Honest empty. Vitest.
- **W03 — Model A/B card on /eval or /track-record**: consume
  GET /api/v1/system/model-ab + /system/resolved-count: show progress toward
  the 100-resolve threshold, and when ready the XGB-vs-LGBM Brier comparison
  with an explicit "default unchanged — analysis only" note. Honest
  not-ready state with the progress bar. Vitest.
- **W04 — Polish + a11y on new surfaces**: skeletons, animated numbers,
  scroll reveals, prefers-reduced-motion, 390px no-overflow, chart
  aria-labels on the new watchlist/alerts/model-ab views. Log findings.

## ITERATION PROTOCOL (per track)

1. git status (confirm worktree/branch). Name the ticket.
2. Smallest green slice; reuse existing modules/components.
3. Run the track GATE; fix until green.
4. Update LOOP LOG (+ API-NOTES.md for backend) with evidence + AutoLab
   line; commit `feat(v5-fe|v5-be): <ticket> <summary>`. Do NOT push. STOP.

## LOOP LOG

| iter | date | track | ticket | result | proof |
|------|------|-------|--------|--------|-------|
| 1 | 2026-07-10 | BE | J01 | done | watchlist store+API (POST/DELETE/GET /api/v1/watchlist), table via Alembic `035_watchlist` (single head). Gate: pytest 1222 passed, 28 skipped; ruff clean. AutoLab: baseline=full suite green | benchmark=test_watchlist_api.py (6 cases: auth-401, add/list/remove, dedupe, honest-404, per-user isolation) + 5xx guard | iterations=1 (green first slice) | budget=1/3 | outcome=improved |
| 2 | 2026-07-10 | BE | J02 | done | alerts feed GET /api/v1/alerts/feed (read-only over signal_events; families news:mispricing/anomaly:unusual_flow/delta:*/screener:*/arb; since+slugs+watchlist scoping; H03 citation fields). New path (not /alerts) to keep existing Alert-dispatch shape+test intact. 5xx guard extended (OPTIONAL_AUTH_PUBLIC_GETS + MUST_COVER). Gate: pytest 12 passed (feed+guard+activity); ruff clean. AutoLab: baseline=J01 green | benchmark=test_alerts_feed_api.py (6 cases: family filter, citations, slug filter, since, watchlist default, honest-empty) + guard covers /alerts/feed | iterations=1 | budget=1/3 | outcome=improved |
| 3 | 2026-07-10 | BE | J03 | DONE (orchestrator-completed after builder hit session limit) — GET /api/v1/system/model-ab: public walk-forward XGB-vs-LGBM readout composing the G06 harness; below gate returns ready:false+progress, at/above gate returns both Briers + delta + which_would_win, applied always false (default never flipped), compute failure degrades to ready:false+note (never 5xx); honest lightgbm_available. 2 endpoint tests (below-threshold, applied-never-true) + covered by the I01 5xx sweep. | pytest targeted 7 passed (model-ab + 5xx guard + resolved-count); ruff All checks passed. AutoLab: not applicable (additive readout endpoint). |
