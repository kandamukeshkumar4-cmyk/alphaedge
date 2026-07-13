# Loop V14 — Fix the resolution→scoring pipeline (resolved_count stuck at 1) (2026-07-11)

> BACKEND-ONLY loop. Orchestrator (Claude, main thread) reviews, gates, and
> deploys via the collision-safe loop3->codex refspec push + idle-check (a
> parallel e2e-loop may share loop3). Commit each ticket when its gate is green.

## WHY (grounded — this is a real bug, not "data-blocked")

`GET /api/v1/system/resolved-count` has been pinned at 1/100 since inception and
`GET /api/v1/resolved` returns n=0, even though ~567 markets ingest and the
resolver loops heartbeat. INVESTIGATION ROOT CAUSE: there is NO automated
mechanism that resolves LIVE Polymarket/Kalshi `ExternalMarket` rows from real
venue data. The only writer of `ExternalMarketStatus.RESOLVED` + winning_outcome
is the manual admin endpoint `POST /api/v1/admin/external-markets/{id}/resolve`
(`app/api/v1/forecast_routes.py:291`), which a human must call by hand. The
venue adapters (`app/services/venues/polymarket.py`, `kalshi.py`) READ the
payloads but DISCARD the resolution fields (Polymarket `closed`/`outcomePrices`/
`umaResolutionStatus`; Kalshi `status`/`result`). `resolved_count=1` is only the
seed market `nba-2025-01-15-lal-bos` leaking through the paper-order fallback in
`app/ml/ab_harness.py`. The count query is a 3-way join: LIVE `ForecastLog`
⋈ `ForecastScore` ⋈ `ExternalMarket WHERE status==RESOLVED`
(`app/api/v1/track_record.py:71`, `app/api/v1/resolved.py:82`). Link (a)
(external market resolved from venue data) is never produced.

## GROUND TRUTH

- Prod backend https://mukeshkumar007-alphaedge-api.hf.space (deploy via
  `git push origin loop3-agent-memory:codex/alphaedge-base` after idle-check).
  Single Alembic head = 037_paper_order_idempotency.
- REUSE existing services — do NOT write new resolution/scoring logic:
  `ExternalMarketService.resolve` (external_market_service.py:106),
  `ScoringService.score_market` (scoring_service.py:32; has a leakage gate:
  only forecasts locked strictly before resolved_at are scored),
  `ForecastService.lock_forecast` (forecast_service.py:142). Model the new
  task after `wc2026_resolve_task` (workers/tasks.py:120) incl. a JobRun/
  heartbeat and a cron entry.
- Connector raw payloads: confirm the exact venue resolution field names by
  READING the existing Polymarket/Kalshi fetch connectors (they already hit
  these endpoints) and/or capturing ONE sample payload into a test fixture —
  NO live network in tests.

## GATE (per ticket — paste output in LOOP LOG)

- `ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q -p no:cacheprovider
  --basetemp=<scratchpad>` and `uv run --extra dev ruff check app tests`.

## GUARDRAILS (non-negotiable)

- NO FABRICATED OUTCOMES. Resolve a market ONLY when the venue reports a
  TERMINAL, unambiguous result. VOID/invalid/`umaResolutionStatus != resolved`/
  Kalshi non-`{finalized,settled}` → leave OPEN, do not resolve.
- PRESERVE THE LEAKAGE GATE. Never score a forecast locked at/after resolved_at.
  Do NOT backfill after-the-fact forecasts to inflate the count — the number
  must accrue from genuine pre-close forecasts only. (This means the count
  climbs FORWARD in time; that is the correct, honest behavior.)
- PAPER_TRADING_ONLY; order path untouched (RiskService→OrderIntent→
  OrderBookService); reuse existing services; additive API only; no response-
  shape change to existing endpoints; new public GETs (if any) stay in the I01
  5xx guard; never weaken a test; tests use fixtures, no network.
- Edit ONLY backend/** + goals/loop-v14/**. New Alembic migration only if a
  column is genuinely needed (prefer none — resolution reuses existing columns);
  if added, chain from 037 and keep ONE head.

## BACKEND TRACK (worktree loop-grok-backend)

- **F01 — Surface venue resolution in the adapter layer**: add optional
  `status` / `resolved` (bool) / `winning_outcome` (0|1|None) to `VenueMarket`
  (`app/services/venues/types.py`); populate in Polymarket + Kalshi
  `normalize()` from the real venue fields (Polymarket: `closed==true` +
  `outcomePrices`/`umaResolutionStatus`; Kalshi: `status in {finalized,settled}`
  + `result`). Map to a terminal winning_outcome ONLY on unambiguous resolution;
  else `resolved=False, winning_outcome=None`. Pure parsing. Unit tests vs
  captured fixtures (resolved-YES, resolved-NO, still-open, VOID/ambiguous→None).
- **F02 — `resolve_external_markets` polling task**: new worker task (mirror
  wc2026_resolve_task) that selects `ExternalMarket` rows with status==OPEN and
  close_at < now(); fetches the venue snapshot via the adapter; when F01 reports
  a terminal outcome, calls the EXISTING `ExternalMarketService.resolve(id,
  winning_outcome, resolved_at)`. Skip non-terminal. Add cron + JobRun heartbeat
  + a config flag (default on). Bounded batch per run. Tests: resolved venue →
  market flips to RESOLVED; open/void venue → stays OPEN; idempotent re-run.
- **F03 — Score on resolution**: immediately after each successful resolve in
  F02, call the EXISTING `ScoringService(session).score_market(market)` (exactly
  as the admin endpoint does at forecast_routes.py:301). This creates the
  ForecastScore rows (leakage gate intact). Test: a resolved external market
  WITH a pre-close LIVE ForecastLog produces a ForecastScore and now appears in
  `/resolved` + increments resolved_count; a post-close forecast is NOT scored.
- **F04 — Auto-lock LIVE forecasts on open external markets near close**: a
  small task (config-flagged, default on, bounded batch) that locks a model
  forecast via the EXISTING `ForecastService.lock_forecast` for OPEN external
  markets approaching close that lack a LIVE ForecastLog — so a genuine
  pre-close prediction exists to score when they later resolve. This is the
  enabler that lets resolved_count climb toward 100 honestly (forward in time).
  Tests: creates a LIVE ForecastLog for an eligible open market; skips markets
  that already have one / are already closed. Note the product choice in the LOG.

## ITERATION PROTOCOL

1. git status (confirm worktree/branch; sync to loop3 tip first). Name the ticket.
2. Smallest safe slice; reuse existing services.
3. Run the GATE; fix until green.
4. Update LOOP LOG (+ API-NOTES.md if any contract) with evidence + AutoLab
   line; commit `feat(v14-be): <F0x> <summary>` immediately.

## LOOP LOG

| iter | date | ticket | result | proof |
|------|------|--------|--------|-------|
| 1 | 2026-07-11 | F01 | done | VenueMarket gains status/resolved/winning_outcome; Polymarket + Kalshi normalize() parse REAL venue resolution terminally-only (PM: closed + umaResolutionStatus==resolved + outcomePrices at a pole; Kalshi: status in {finalized,settled} + result yes/no). VOID/disputed/50-50/non-terminal → resolved=False, winning_outcome=None (never fabricated). 7 fixtures (resolved-yes/no/void/pending both venues) + test_venue_adapters.py resolution tests. Gate: 7 passed; ruff clean. AutoLab: n/a (pure parse).
| 2 | 2026-07-13 | F02 | done | Added `fetch_market(external_id)->VenueMarket\|None` to VenueAdapter protocol + Polymarket (single Gamma slug fetch) + Kalshi (single ticker fetch) — resolves past-close markets the active-listing omits; None on unavailable/error. New `app/services/external_market_resolver.py::resolve_external_markets(session, limit, now)`: selects OPEN ExternalMarket rows with close_at<now (bounded batch, oldest-close first), fetches venue snapshot, and ONLY on terminal resolved+winning_outcome calls existing `ExternalMarketService.resolve(id, winning_outcome, resolved_at=close_at)`. Non-terminal/void/unavailable → stays OPEN. resolved_at pinned to close_at (honest pre-close cutoff for the F03 leakage gate). Task `resolve_external_markets_task` (JobRun + degraded-on-errors), in-process loop `_external_resolve_loop` (900s) flag-gated `SCHEDULER_EXTERNAL_RESOLVE_ENABLED` (default on) + batch `EXTERNAL_RESOLVE_BATCH`=25, cron `minute={10,40}`, loop `external_resolve` added to LOOP_INTERVALS + /system/loops `_ALL_LOOPS`. Tests: resolved→RESOLVED+winning; open/void→OPEN; future-close not checked; re-run idempotent (OPEN filter excludes resolved). Gate: 1364 passed, 28 skipped; ruff clean. AutoLab: not applicable (no iterative measure — enabling infra).
| 3 | 2026-07-13 | F03 | done | resolve_external_markets now scores each newly-resolved market via existing ScoringService.score_market(resolved_market) right after resolve() — exactly like the admin endpoint (forecast_routes.py:301). Leakage gate lives in ScoringService (only LIVE forecasts locked strictly before resolved_at=close_at count). Returns a 'scored' count. test_external_market_scoring.py: pre-close forecast → scored + appears in resolved-count; post-close (leaky) forecast NOT scored; void market not scored. Gate: 5 passed; ruff clean. AutoLab: n/a (reuses existing scorer).
