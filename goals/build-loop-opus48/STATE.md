# Opus 4.8 Loop — post-demo hardening + intelligence depth (STATE)

Runner: Claude Opus 4.8 (or stronger). One ticket per iteration. This file is
the loop's memory — update it EVERY iteration before ending the session.
Started 2026-07-06, immediately after PR #40 merged (demo reliability + E2E
smoke harness + deployed-AI root causes).

## Context you inherit (read before picking a ticket)

- PR #40 fixed: HF Space sleep (demo-uptime.yml cron), missing LLM keys in the
  deploy secret sync, assistant NIM gate, stale frontend (STATIC_EXPORT=1 SWA
  deploy), live-market links 404ing on the static host (marketHref/briefHref).
- The E2E smoke harness is the loop's main verification asset:
  `cd backend && uv run --extra dev pytest tests/smoke/ -q --base-url <url>`
  (15 tests; `ALPHAEDGE_EXPECT_LLM=1` makes fallback-mode AI a hard failure).
- Deployed demo: API https://mukeshkumarkanda-alphaedge-api.hf.space, frontend
  https://proud-meadow-01b42b810.7.azurestaticapps.net (Azure SWA), DB Neon.
- Queued loop-b2 tickets (B02/B03/B05/B06) move here as O04/O05/O06/O03.

## Goal (the recursive condition)

The demo is trustworthy on any given day without manual babysitting, AND the
intelligence layer gets measurably deeper: every signal source (price, whale,
news, weather, screeners) lands in signal_events and is visible in the UI, the
AI layer runs on a real LLM in production with citations, and model choices
are decided by measured Brier — never by vibes.

## Hard guardrails (violating any = failed iteration, revert)

1. `PAPER_TRADING_ONLY=true` everywhere. No real-money paths, ever.
2. Order path stays `RiskService → OrderIntent → OrderBookService`; LLM/agent
   code never submits raw orders.
3. Never fabricate data or metrics. Demo fixtures only behind the DemoChip
   when the API returns nothing. "Live-verified" claims need pasted evidence
   (IDs, timestamps) from a running stack.
4. Never game a benchmark or weaken a gate/test/threshold to go green.
5. No code copied from AGPL/commercial tools (FinceptTerminal, CloddsBot…) —
   clean-room ideas only.

## The gate (run ALL before marking any ticket DONE)

```bash
cd backend  && uv run --extra dev pytest -q && uv run --extra dev ruff check app tests
cd frontend && npm run typecheck && npm run lint && npm test && npm run build
# E2E (local stack: Postgres + alembic upgrade head + uvicorn):
cd backend  && uv run --extra dev pytest tests/smoke/ -q --base-url http://127.0.0.1:8000
```
Plus for UI tickets: page renders in a browser with zero console errors.
Plus for deployed tickets: smoke suite against the HF Space URL.

## Stop conditions

- SUCCESS: all tickets DONE or BLOCKED-ON-USER, gate green.
- REORGANIZE: 3 consecutive iterations with no ticket newly DONE → stop,
  write a post-mortem here, re-plan the ticket order.
- Budget: 1 ticket per iteration; split tickets that don't fit a session.

## Maker/checker split (required)

Implement with one agent; before marking DONE, spawn a separate verifier
subagent (fresh context) that re-runs the gate and adversarially reviews the
diff against the guardrails. Verifier verdict goes in Notes.

## Tickets (priority order)

| ID | Ticket | Status | Notes |
|----|--------|--------|-------|
| O01 | **Deployed AI live-verified**: after the owner adds `LLM_PROVIDER`/`NIM_API_KEY`/`LLM_MODEL` GH secrets and the sync deploy runs, run the smoke suite vs the HF Space with `ALPHAEDGE_EXPECT_LLM=1`; verify brief `generator=llm` + assistant gives a real LLM reply with the analysis-only banner. Then flip the demo-uptime AI check from warn-only to hard-fail (it should stay warn-only until the keys exist). | BLOCKED-ON-USER (needs GH secrets) | The 2026-07-06 dispatch of "Deploy Backend to HF Space" ran with sync_runtime_secrets=true — check whether it synced any AI keys; if the owner has added them since, this ticket unblocks itself. |
| O02 | **Portfolio net positions GROUP BY slug/side**: the known aggregation issue (see root `STATE.md` Next Queue + portfolio-monitor agent). Group paper_orders by (market slug, side), not id, so partial closes/re-buys net correctly. Unit-test the math incl. the E12 settlement semantics. | DONE 2026-07-06 (already-fixed, regression-locked) | INVESTIGATED not blindly implemented (CLAUDE.md truth-first): `_load_paper_orders` in portfolio.py ALREADY does `GROUP BY po.slug, po.side, po.outcome` (not id), and on the JWT path `side = outcome.upper()` so side is a deterministic function of outcome — netting of partial closes + re-buys is already correct, and `get_open_paper_position` filtering by slug+outcome is equivalent. The stale root-STATE ticket described a bug that was already fixed. Added the one missing coverage case (`test_rebuy_after_partial_close_nets_into_one_weighted_position`): buy 10@0.40 → sell 4@0.50 → buy 10@0.60 nets to ONE row, 16 shares, BUY-weighted avg 0.50, cost 8.0, realized 0.40 preserved. Passes on real Postgres (test_position_close 12/12). No production code changed — no fabricated diff. |
| O03 | **Expiry-fade + momentum screeners** (was B06): deterministic screeners over odds_snapshots (fade near-expiry longshots; momentum continuation), exposed as `GET /api/v1/signals/screeners` + persisted as `signal_type=screener:*` SignalEvents. Signals only — no order path. Clean-room. | DONE 2026-07-06 | New pure module `app/signals/screeners.py` (screen_expiry_fade + screen_momentum, both pure/injectable). `SignalsService.screeners()` loads odds_snapshots series + Market.lock_at, runs both, persists `screener:expiry_fade`/`screener:momentum` SignalEvents (headline_eligible at strength≥0.5). `GET /api/v1/signals/screeners?screen=all|expiry_fade|momentum` (auto-covered by the E2E GET sweep). 18 tests: 13 pure-rule (up/down/reversal/small-move/too-few/flat/cap; longshot/non-longshot/far-expiry/missing-close/dust/depth) + 5 DB (finds+persists both, screen filter, endpoint 200/shape, bad-screen 400, empty). ruff clean. No order path touched. |
| O04 | **Weather edges → SignalEvents + feed** (was B03): today the weather desk is API/page-only; emit `delta:weather_edge` SignalEvents so edges appear in /signals + ticker + engine room. | TODO | Reuse persist_deltas (require_market=False — weather markets are Kalshi externals). |
| O05 | **Weather forecast-vs-actual logging** (was B02): nightly task logging NWS forecast vs actual so bucket sigma can be learned once weeks of rows accumulate. | TODO | Rows-accumulate benchmark; no model change until data exists (anti-benchmark-gaming). |
| O06 | **Deep daily digest on reasoning model** (was B05): route the daily digest to `LLM_MODEL_DEEP` (nemotron-49b class, ~19s fine for cron); per-feature model routing in config; digest cites news/whale/macro evidence. | TODO | Needs NIM key live (after O01). Add `LLM_MODEL_DEEP` setting + fallback to LLM_MODEL. |
| O07 | **Chart light-mode theming** (E-chart-theme debt): lightweight-charts grays/textColor are hardcoded — re-theme PriceChart on `.light` toggle (read CSS vars or theme prop). | TODO | Browser-verify both themes; zero console errors. |
| O08 | **Small-debt batch**: `useApiHealth` unit test (E-test-debt) + unconditional KalshiConnector instantiation cleanup in `run_live_tick_once` (E01 minor). | TODO | Two tiny items, one iteration. |
| O09 | **LightGBM vs XGBoost A/B on real data** (E06 continuation): run walk-forward Brier once ≥100 resolved outcomes exist in prod DB; flip `ML_MODEL_TYPE` default ONLY if LightGBM measurably wins. | BLOCKED-ON-DATA (~17 resolved as of 2026-07-03; recheck count each iteration) | Record both Briers in the AutoLab line regardless of outcome. |
| O10 | **FIFA CSVs** → `backend/app/data/fifa/` unlocks 7 skipped tests + WC2026 model training. | BLOCKED-ON-USER (owner must supply CSVs) | See `docs/handoff/CODEX-fifa-track.md`. |

## Iteration protocol (read this every run)

1. Read this file + `AGENTS.md` + `goals/build-loop-backend2/STATE.md` (B08
   row documents the demo root causes).
2. Pick the FIRST ticket that is TODO and unblocked (recheck BLOCKED-* —
   O01/O09 can unblock themselves). Announce it in one line.
3. Implement the smallest shippable slice. Reuse existing modules; UI stays
   in the Questflow design language (quest/* + tailwind tokens).
4. Run the FULL gate. Fix until green — persist (AutoLab), don't thrash.
5. Spawn verifier subagent → verdict in Notes.
6. Update the ticket row + append one AutoLab line below. Commit
   `feat(opus-loop): <ID> <summary>`, push, PR per the remote workflow.

## AutoLab log

- 2026-07-06 bootstrap: baseline = PR #40 merged, ALL CI green (backend
  1050 passed/16 skipped + ruff, frontend typecheck/lint/61 tests/build,
  SWA deploy green, smoke 15/15 vs live local stack) | loop authored with
  10 tickets (2 blocked-on-user, 1 blocked-on-data) | outcome = ready.
