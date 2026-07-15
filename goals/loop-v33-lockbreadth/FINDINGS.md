# Loop V33 — FILED FINDINGS (not implemented here)

Filed per GOAL.md B2 ("file findings — do NOT hack predictions") and
DIR-V33-001.3 ("anything needing model/feature work gets FILED, not
implemented"). Each item is out of B2's config-only scope and needs its own
ticket with its own review.

---

## F1 — `external_markets` has no automated supply (root cause of zero breadth)

> **STATUS: RESOLVED by B2' (commit on this branch).** The orchestrator
> redirected B2 from config tuning to implementing this bridge (DIR-V33-002), so
> F1 became the ticket rather than a filing. Kept here as the root-cause record;
> the constraints below are what B2' implements and tests.

**Severity: blocks the 100-resolution threshold entirely.** Evidence: B1 in
`STATE.md`.

The autolock worker selects from `external_markets`. Nothing automated ever
writes that table:

- Only writer: `ExternalMarketService.resolve_url*`
  (`backend/app/services/external_market_service.py:73`).
- Only callers: `POST /api/v1/markets/external/resolve-url`
  (`forecast_routes.py:109`) and `POST /api/v1/forecasts`
  (`forecast_routes.py:126`) — both forecaster-driven.
- The live-ingest loop writes only the `Market` catalog
  (`live_market_ingest.py:205`, `kalshi_live_ingest.py:242`) and never
  constructs an `ExternalMarket`.

Measured: 99 real markets ingested locally → 0 `external_markets` rows.

`POST /forecasts` additionally locks a forecast in the same request, so with
`mode=LIVE` the row it creates is born already excluded by
`~live_forecast_exists`. The only row that can ever be an autolock candidate is
one registered via `resolve-url` with no follow-up forecast — no automated
caller does that.

**Proposed fix (needs its own ticket — NOT config, and NOT done here):** a
catalog→external supply bridge that mirrors ingested `Market` rows into
`external_markets` for venue-backed markets.

Non-negotiable constraints for whoever picks this up:

1. **Only mirror markets with a real, venue-sourced `close_at`.** A row with no
   provable close time must never enter `external_markets` — the pre-close
   guarantee is unprovable without it, and filter 2 exists for exactly this
   reason. Do not "infer" a close time.
2. **Mirror identity must be exact.** `platform` + `external_id` must be the
   real venue identifiers so `get_adapter(...).fetch_snapshot(external_id)` and
   the venue resolver resolve the *same* market. A synthetic or slug-derived id
   would silently mis-resolve — i.e. score a forecast against the wrong outcome.
   Note the local catalog uses a `pm-` slug prefix (`live_market_ingest.py:31`);
   the bridge must carry the venue id, not the slug.
3. **Never set `winning_outcome`/`resolved_at`.** The bridge creates OPEN rows
   only; resolution stays exclusively with the existing venue resolver.
4. **Idempotent.** Keyed on the existing unique
   `(platform, external_id)` index; re-ingest must update, never duplicate.
5. **Bounded**, like every other loop pass.
6. Kalshi is currently a no-op locally (`imported=0, skipped=200` — see B1), so
   validate per-venue rather than assuming both venues supply rows.

Expected effect: this is the only change that can move stage 0 above zero, and
therefore the only one that can move `resolved_count`.

---

## F4 — Horizon is now the binding filter (first data-justified tune) — NEW

Filed by B2' (the bridge), which made F1 obsolete by implementing it.

With supply finally flowing, the funnel has a real shape for the first time.
Measured locally against real Polymarket data after one bridge pass (25 rows):

```
0_external_markets_total   25
1_status_open              25
2_has_close_at             25
3_close_at_in_future       25
4_within_horizon           14   <- 11 excluded by the 24h horizon
5_lacks_live_forecast      14
6_after_batch_cap          14
biggest_exclusion: 3_close_at_in_future -> 4_within_horizon, excluded=11
```

So `EXTERNAL_AUTOLOCK_WINDOW_SEC=86400` now excludes **11 of 25** bridged
markets — it is the binding filter, exactly as B2 predicted it would become once
stage 0 was non-zero.

**Not tuned here** — B2 was redefined to the bridge (DIR-V33-002) and a horizon
change is a separate, reviewable decision with a real trade-off: locking earlier
means forecasting with less information, which costs accuracy on a track record
whose value is trust. Now that the drop is *measured* rather than inferred, that
trade-off can be made on data. **Ask:** a follow-up ticket to pick the horizon
against measured stage-3→4 drop vs. Brier impact, rather than widening it
reflexively.

---

## F2 — Prod autolock funnel is not observable (blocks data-justified tuning)

The prod stage-0 count cannot be measured from outside:

- `/api/v1/system/loops` exposes autolock liveness but **not** the JobRun
  summary (`candidates`/`locked`/`skipped`/`errors`) the worker already records
  (`forecast_autolock.py:229-237`).
- That summary is only reachable via `/api/v1/admin/jobs`, which needs the prod
  `ADMIN_API_KEY`.

So prod evidence for B1 is strong but indirect (`backfill/markets=0`,
`eval/evaluations=[]`, `eval/aggregates.market_count=0`, `clv-track-record`
empty). **Ask, either:**

- run `uv run --extra dev python scripts/autolock_funnel_snapshot.py` against a
  read-only prod `DATABASE_URL` (SELECTs only), or
- surface `candidates`/`locked`/`skipped` from the latest
  `forecast_autolock_task` JobRun in `/api/v1/system/loops`.

Until then, any horizon tune in prod would be justified by inference rather than
measurement — which DIR-V33-001.2 forbids. See B2 in `STATE.md`.

---

## F3 — `resolved_count` silently falls back to paper orders

`count_resolved_outcomes` (`backend/app/ml/ab_harness.py:43-52`) returns
`_resolved_forecast_rows` when non-empty, else falls back to
`_from_paper_orders`. The public `/api/v1/system/resolved-count` readout does not
say which source produced the number.

Prod currently reports `resolved_count=1` while `backfill/markets=0`,
`eval/evaluations=[]` and `clv-track-record` is empty — consistent with the
number coming from the paper-orders fallback, i.e. the *forecast-scored* count is
plausibly 0.

Not a correctness bug (the fallback is intentional and documented in-code), but
the A/B gate's "1 of 100" is measuring a different population than the loop is
trying to accrue. **Ask:** label the source in the readout (e.g.
`source: "forecast_scores" | "paper_orders"`) so the threshold is unambiguous.
Read-only/additive; not done here (outside V33 ownership).
