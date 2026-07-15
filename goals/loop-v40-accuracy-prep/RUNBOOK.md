# Loop V40 — Accuracy-Loop Readiness RUNBOOK

> Analysis/spec only. No code. Branch `loop40/accuracy-prep` from `64a74f7`
> (the V33 merge). Prepared by the V33 runner.
>
> **All prod numbers below are MEASURED read-only at 2026-07-15 ~21:53–22:15Z**
> against `https://alphaedge-api-production-b9db.up.railway.app`, and are
> labelled `[measured]`. Anything forward-looking is labelled `[projected]` with
> its arithmetic shown. Nothing here is estimated-and-presented-as-fact.

## TL;DR — three things to know before the accuracy loop starts

1. **V33 is confirmed working in prod.** `[measured]` `external_markets` went
   `1 → 26` on the bridge's first pass (25 bridged, exactly one batch). The
   funnel is off stage 0 in production, not just locally.
2. **The A/B is NOT ready, and `resolved_count >= 100` will not make it ready.**
   Two independent blockers, both structural, both invisible from the gate:
   `lightgbm_available: false` in prod, and **the gate counts a different
   population than the A/B trains on** (§C-1). This is the same shape of bug as
   V33 B1 — a counter watching one table while the consumer reads another.
3. **The first 100 resolved outcomes will be badly non-representative**
   (§C-2). `[measured]` the only markets currently inside the lock horizon are
   Crypto 2 / Economics 1 — zero sports — while the model's features are
   Elo/rest/back-to-back. Brier on that set does not measure what we want.

---

# A. First-24h funnel health check

## A-0. What is already true `[measured]`

| Signal | Value at 2026-07-15 ~22:12Z | Reading |
|---|---|---|
| `/api/v1/system/loops` → `external_market_bridge` | `running=true, status=ok` | bridge deployed + alive |
| `forecast_autolock.detail` | `external=26 open=26 pre_close=25 in_horizon=3 eligible=3 selectable=3 biggest_drop=3_close_at_in_future->4_within_horizon:22` | funnel off stage 0; horizon now binding |
| `/api/v1/system/resolved-count` | `resolved_count=1, source=paper_orders_fallback, forecast_scored_count=0` | V33 B2'c live; no forecast scored **yet** |
| catalog `/api/v1/markets?limit=500` | 740 rows; 361 bridge-eligible (open + polymarket + future `lock_at`) | supply pool for the bridge |
| `/api/v1/system/model-ab` | `ready=false, lightgbm_available=false` | **A/B blocked — see §C-1** |

## A-1. The signals to inspect tomorrow, in order

All are GET, no admin key, no mutation.

### 1. Bridge growth curve — `forecast_autolock.detail` → `external=N`

The bridge registers ≤25/pass every 900s and the eligible pool is 361
`[measured]`.

`[projected]` 25/pass × 4 passes/hr = 100/hr → the pool saturates in
**~15 passes ≈ 3.7h**. So by T+24h `external` should have plateaued near
**~360–420** (the pool, plus whatever live ingest adds; ingest runs every 300s).

| `external=N` at T+24h | Verdict |
|---|---|
| **350–450, roughly flat vs T+6h** | **HEALTHY** — pool saturated, tracking ingest |
| 26–100 | **STUCK** — bridge is running but mostly skipping. Go to §A-2. |
| exactly 26, unchanged | **STUCK HARD** — no bridging since the first pass |
| > 600 and still climbing steeply | **INVESTIGATE** — ingest inflow or duplicate rows; cross-check §A-3 |

### 2. `in_horizon` / `eligible` — do NOT read a small number as broken

`[measured]` `in_horizon=3` of 25 `pre_close`. **This is expected and healthy.**
Markets flow *into* the 24h window as their close approaches; at any instant
most bridged markets are further out than 24h. `eligible` is a snapshot of a
queue, not a backlog.

- `eligible` in **0–40** at any given pass: normal.
- `eligible` pinned at **0 for >24h while `pre_close` is large**: suspicious —
  it means nothing is approaching close, which contradicts a live catalog.
  Check that `pre_close` is not itself frozen (a stale catalog).
- `eligible` **> 25 sustained across many passes**: the batch cap is now the
  binding filter and markets could age out. `[projected]` capacity is
  25 × 96 passes/day = **2400/day**, far above any plausible inflow, so this
  should not happen; if it does, that is the one case where raising
  `EXTERNAL_AUTOLOCK_BATCH` is justified — and see §C-4 before touching it.

### 3. First LIVE ForecastLog

There is no public count of `ForecastLog`. Use these proxies:

- **`forecast_autolock.detail`**: after a pass that locks, the *next* pass's
  `eligible` should drop by the number locked (they now fail
  `~live_forecast_exists`). Watching `eligible` fall while `pre_close` holds
  steady **is** the observation that locking is happening.
- `[projected]` with `eligible=3` at 22:12Z, the first locks should occur on the
  **next autolock pass (~22:27Z)** and `eligible` should read `0` shortly after,
  then oscillate 0–small as new markets enter the window.
- **STUCK**: `eligible` stays > 0 across ≥3 consecutive passes with no decline →
  autolock is selecting but failing to lock (adapter/prediction path). The
  durable evidence is the `forecast_autolock` JobRun summary
  (`locked`/`skipped`/`errors`) via admin `/api/v1/admin/jobs`.

### 4. The resolved-count source flip — **the single most important signal**

```
/api/v1/system/resolved-count
  now  [measured]: {"resolved_count": 1, "source": "paper_orders_fallback", "forecast_scored_count": 0}
  want [projected]: {"source": "forecast_scores", "forecast_scored_count": >= 1}
```

The flip requires the full chain: bridged → locked pre-close → market closes →
`external_resolve` settles it from venue data → scoring writes a `ForecastScore`.

`[projected]` timing: the markets inside the horizon now are daily crypto /
economics markets closing at ~16:00Z `[measured: pm-bitcoin-above-60k-on-july-16-2026,
lock_at 2026-07-16T16:00:00Z]`. `external_resolve` runs every 900s. So the first
flip is plausible **within ~18–24h**, and near-certain within 48h.

| Observation | Verdict |
|---|---|
| `source` flips to `forecast_scores`, `forecast_scored_count >= 1` within 48h | **HEALTHY — V33 fully validated end-to-end in prod** |
| still `paper_orders_fallback` at **T+48h** | **STUCK** — go to §A-2. Something between lock and score is broken. |
| `forecast_scored_count` climbing but `resolved_count` not | impossible by construction (`count` == forecast rows when non-empty) — if seen, file a bug against `resolved_outcomes_breakdown` |

**Do not celebrate `resolved_count` climbing while `source` is still
`paper_orders_fallback`** — that is the paper-orders population, not this loop's
work. The `source` field exists precisely to stop that misreading (V33 B2'c).

## A-2. If STUCK — diagnosis order (cheapest first)

1. **Is it a restart artifact, not a fault?** `[measured, learned the hard way]`
   heartbeats live in an **in-memory** registry (`app/observability/loop_state.py`)
   and every loop sleeps **900s before its first pass**. After any deploy/restart
   `/api/v1/system/loops` legitimately shows `status=never, detail=None` for up to
   15 minutes. Check `/api/v1/system/metrics` → `uptime_seconds` **first**:
   if `uptime < 900`, there is nothing wrong; wait.
2. **Am I reading a pre-bridge snapshot?** `[measured]` in-process, autolock's
   funnel snapshot fired at `21:53:03` and the bridge at `21:53:04` — autolock
   measured **1s before** the bridge's first pass and correctly reported
   `external=1`. A single fresh-boot reading can look starved when it is not.
   **Always compare two consecutive autolock passes** before concluding anything.
   (I initially misread exactly this and had to correct myself.)
3. **Are there multiple replicas?** `[measured]` one poll returned
   `uptime=700s` alongside a heartbeat timestamped *before* that uptime window —
   consistent with per-process registries behind a load balancer. If so,
   `/api/v1/system/loops` is **non-deterministic per request**. Poll several
   times; treat the DURABLE `JobRun` table as truth, not the heartbeat.
4. **Bridge candidates vs skips** — needs admin `/api/v1/admin/jobs`, filter
   `external_market_bridge_task`:
   - `candidates=0` → nothing eligible: check `Market.external_slug` is populated
     and `source in (polymarket, kalshi)` and `lock_at > now`.
   - `candidates>0, bridged=0, skipped=N` → the venue re-read is failing. The
     bridge calls `get_venue_adapter(...).fetch_market(slug)` (single-market
     Gamma fetch), which is a **different endpoint** from live ingest's bulk
     `list_active_markets` — one can be rate-limited/blocked while the other
     works. This is the most likely silent failure.
   - `errors>0` → read the logged warning per market.
5. **`live_ingest` health.** `[measured]` at 21:57:04Z `live_ingest` reported
   `status=error, detail="live ingest pass failed"`. If ingest is failing, the
   catalog goes stale and the bridge's pool stops refreshing. **Worth checking on
   its own merits — flagged here, not diagnosed.**

## A-3. Observability gap to close (recommend as a V40 follow-up ticket)

**The bridge's own heartbeat is silent**: `external_market_bridge.detail=None`
`[measured]`, because V33 B2'b put the funnel on `forecast_autolock` only. So
"bridge alive" is visible but "bridge bridging" is **not** — the exact
distinction §A-2.4 needs, and it currently requires an admin key.

This is a gap in my own V33 work. The fix is small and symmetric: put the bridge
summary (`candidates`/`bridged`/`skipped`/`errors`) on its heartbeat `detail`,
exactly as autolock does. Recommend as a one-ticket follow-up.

---

# B. AutoLab calibration loop spec — execute the day `resolved_count >= 100`

**Read §C first.** Two blockers must clear before this spec produces a
meaningful result; running it while they stand would produce a number that looks
like a model comparison and is not one.

## B-1. Binding rules (from retired D5/E06 + `AGENTS.md`)

1. **Never train on post-close information.** See §B-3 — ordering by prediction
   time is *necessary but not sufficient*.
2. **Activation is a human decision.** `run_walk_forward_ab` never flips the
   default and must not be changed to
   (`ab_harness.py` docstring: *"HARD GUARDRAIL: this harness NEVER flips the
   default model"*). The deployed model stays whatever `ML_MODEL_TYPE` says.
3. **Never game the benchmark.** E06's precedent is the standard to meet: it
   measured XGB `6.1e-4` vs LGBM `5.8e-10` on a synthetic fixture and
   **refused to declare a winner** because the problem was trivially separable.
   A number that cannot discriminate is not a result. Report it and stop.
4. **Never weaken** `PAPER_TRADING_ONLY`, the order path, the leakage gate, or
   any V33 guarantee to make a metric move.

## B-2. Exact data queries

### The gate (already implemented — do not re-derive)

`app/ml/ab_harness.py::count_resolved_outcomes` → `resolved_outcomes_breakdown`
→ `app/api/v1/track_record.py::_resolved_forecast_rows`:

```sql
-- scored LIVE forecasts on RESOLVED external markets
SELECT fl.user_probability, fs.actual_outcome, fs.scored_at
FROM forecast_logs fl
JOIN forecast_scores fs   ON fs.forecast_id = fl.id
JOIN external_markets em  ON em.id = fl.external_market_id
WHERE fl.mode = 'live' AND em.status = 'resolved';
```

**Gate condition:** `source == "forecast_scores"` AND `forecast_scored_count >= 100`.
Not `resolved_count >= 100` — that can be satisfied by the paper-orders fallback
(§C-1). **This is the single most important correction in this runbook.**

### Splitting model forecasts from human forecasts

The query above mixes both. Autolocked (model) forecasts are identified by:

- `forecast_logs.forecaster_id = AUTOLOCK_FORECASTER_ID`
  (`uuid5(NAMESPACE_URL, "alphaedge:model-autolock:v1")`, `forecast_autolock.py:36`), or
- `snapshot_metadata->>'lock_origin' = 'model_autolock'` (`forecast_autolock.py:153`).

`user_probability` on those rows is the **model's** probability
(`prediction.model_prob`), not a human's. Report model and human populations
**separately** — pooling them measures neither. Also carried per row:
`model_provisional`, `clv_gate_passed`.

### The A/B training matrix (⚠ different population — see §C-1)

`app/ml/snapshot_dataset.py::load_resolved_snapshot_feature_matrix`:

```sql
SELECT os.*, m.*
FROM odds_snapshots os
JOIN markets m ON m.slug = os.market_slug
WHERE m.status = 'resolved' AND m.winning_outcome IS NOT NULL
ORDER BY os.market_slug, os.captured_at;
```

Note the tables: `odds_snapshots` × `markets` (**catalog**). Not
`external_markets`, not `forecast_scores`.

## B-3. Split design that respects lock timestamps

**The non-obvious part. Sorting by `locked_at` is not enough.**

The honest constraint is: *a prediction evaluated at time `T` may only be scored
by a model trained on outcomes that were already KNOWN at `T`.* An outcome is
known only once its market **resolved**, not once the forecast was locked.

Because market durations vary (a daily bitcoin market resolves in hours; an
election market in months), `locked_at` order and `resolved_at` order are
**different orderings**. Sorting by `locked_at` and training on the first N rows
will happily train on markets that had not yet resolved at the eval point —
lookahead, silently.

**Rule.** For an eval fold whose earliest lock time is `T_eval_min`:

```
train_set = { forecasts f : f.market.resolved_at < T_eval_min }
eval_set  = { forecasts f : f.locked_at >= T_eval_min }
```

- Order folds by `locked_at` (prediction time), but **filter the training set by
  `resolved_at`**, not by `locked_at`.
- Add an **embargo** between train and eval (the trainer already supports
  `embargo_size`, `trainer.py:137`) to absorb resolution-time jitter.
- Drop any row where `locked_at >= close_at` — V33 makes this impossible for
  autolocked rows, but assert it rather than assume it; a violation is an
  incident, not a data-cleaning step.
- `[measured caveat]` `_resolved_forecast_rows` returns `scored_at`, **not**
  `locked_at` or `resolved_at`. `scored_at` is when the grader ran — an artifact
  of worker scheduling, not of information availability. **Do not order on
  `scored_at`.** The A/B needs a query returning `locked_at` + `resolved_at`;
  today's helper does not expose them.

Windows: `/api/v1/system/model-ab` currently passes `train_window_size=4,
eval_window_size=2` (`system.py:199-200`), the canonical feature-matrix
walk-forward windows. At n≈100 those are reasonable; state them in the report
rather than tuning them to a nicer number (that is benchmark-gaming).

## B-4. Reporting format

Report **both arms, always**, win or lose:

```
AutoLab A/B — walk-forward XGBoost vs LightGBM
  gate:            forecast_scored_count = <n>  (source=forecast_scores)  [>= 100 required]
  population:      model-locked forecasts only (forecaster_id=AUTOLOCK_FORECASTER_ID); humans reported separately
  folds:           <k> (train_window=4, eval_window=2, embargo=<e>), ordered by locked_at, trained on resolved_at < T_eval_min
  xgboost:         Brier <x.xxxxxx>   ECE <x.xxxx>   n_eval <n>
  lightgbm:        Brier <x.xxxxxx>   ECE <x.xxxx>   n_eval <n>
  lightgbm_available: <true|false>    used_fallback_xgboost: <true|false>
  discriminating:  <yes|no — and why>
  verdict:         <no winner declared | lightgbm wins by <d> | xgboost wins by <d>>
  default_model:   xgboost (UNCHANGED — activation is a human decision)
  caveats:         <see B-5>
```

- **Brier**: mean squared error of the probability vs the 0/1 outcome, reported
  to 6 dp, out-of-sample only.
- **ECE**: equal-width bins, reusing `CALIBRATION_BINS` from `app.forecasting`
  (the same constant `track_record.py:40` imports, so the A/B and the public
  track record bin identically — do not hand-roll a second binning),
  report per-bin `count / mean_predicted / observed_frequency` alongside the
  scalar — a scalar ECE over 100 points hides everything.
- If `lightgbm_available == false`, the run compares XGBoost to an
  XGBoost fallback. **Report `used_fallback_xgboost: true` and declare NO
  winner.** `build_classifier` falls back silently; the readout must not.

## B-5. Honest minimum-sample caveats

State these in the report, every time — they are not boilerplate, they are the
reason a 100-sample A/B can mislead:

1. **n=100 is small for Brier.** Two models differing by ~0.01 Brier are not
   separable at n=100; the standard error swamps the difference. Report the
   difference **with an uncertainty interval** (bootstrap over eval rows — the
   trainer already exposes `edge_bootstrap_samples`) and refuse to call a winner
   whose interval crosses zero.
2. **Effective n < nominal n** whenever outcomes are correlated (§C-2). 100 daily
   bitcoin-threshold markets on the same asset are nowhere near 100 independent
   observations.
3. **`track_record.py` already treats n < 30 as `thin_data`**
   (`THIN_DATA_THRESHOLD = BRIER_MIN_SAMPLE`, `track_record.py:55`;
   `[measured]` prod returns `"thin_data": true, "thin_data_threshold": 30`).
   100 clears that flag
   but is still thin for *model selection*, which is a harder question than
   "is the track record presentable".
4. **The 100 gate is a floor, not a green light.** It was chosen (E06/O09) as
   "enough to stop being obviously meaningless", not as "enough to decide".
   If the data is concentrated (§C-2), the right call at 100 is **wait**, and say
   so — exactly as E06 refused to call the synthetic result.

---

# C. Risk register — how the accrued data could be silently biased

Ordered by severity. **C-1 and C-2 are blockers**: at 100 they would each,
independently, make the A/B a number that looks meaningful and is not.

## C-1. ⚠ BLOCKER — the gate and the A/B measure DIFFERENT POPULATIONS

`/api/v1/system/model-ab` gates on `resolved_count` and then trains on
`load_resolved_snapshot_feature_matrix` (`system.py:189-199`):

| | Gate (`resolved_count`) | A/B training matrix |
|---|---|---|
| tables | `forecast_scores` × `forecast_logs` × **`external_markets`** | `odds_snapshots` × **`markets`** (catalog) |
| grows via | V33 bridge → autolock → resolve → score | odds-snapshot capture on catalog markets |

**`resolved_count >= 100` therefore says nothing about how many training rows the
A/B has.** The gate could open with an empty or tiny feature matrix; equally the
matrix could be large while the gate is shut. Nothing connects them.

This is **structurally the same defect as V33 B1** — a counter watching one table
while the consumer reads another. I flag it with some confidence because I just
spent a loop on its twin.

**Checks before trusting the A/B:**
- Assert `len(df) >= 100` **independently** of `resolved_count`, and report both
  numbers side by side.
- Confirm the A/B's markets are the ones this loop accrued. If the intent is to
  grade *the bridged/locked forecasts*, the A/B needs a feature matrix built from
  `external_markets` + `forecast_logs`, which **does not exist today**.
- **Decide and record which population the 100-gate is supposed to govern.**
  Right now it governs neither cleanly. This is a design question for the
  orchestrator, not something to paper over in a query.

## C-2. ⚠ BLOCKER — the accrued data is concentrated and feature-mismatched

`[measured]` of 361 bridge-eligible markets:

| Category | n | | Category | n |
|---|---|---|---|---|
| Politics | 91 | | Sports | 34 |
| Crypto | 51 | | Culture | 28 |
| Tech | 49 | | FIFA WC2026 | 20 |
| Economics | 47 | | **sports-ish total** | **95 (26%)** |
| NBA | 41 | | **non-sports total** | **266 (74%)** |

`[measured]` markets **inside the 24h lock horizon right now: Crypto 2,
Economics 1 — zero sports.**

`[measured]` `FEATURE_COLUMNS` (`app/ml/features.py:7`) is sports-shaped:
`home_elo_pre`, `away_elo_pre`, `elo_diff`, `home_rest_days`, `away_rest_days`,
`home_back_to_back`, …

**So the markets accruing outcomes fastest are precisely the ones the feature set
cannot describe.** For "will bitcoin be above 60k on July 16", `elo_diff` is not
merely unhelpful — it is undefined.

**Worse — accrual velocity is skewed by close cadence, not by importance.**
`[measured]` the horizon queue is daily threshold markets
(`pm-bitcoin-above-60k-on-july-16-2026`, `...-68k-...`, `pm-elon-musk-of-tweets-...`).
Daily markets resolve **daily**; an election market resolves once. `[projected]`
the first 100 scored outcomes will therefore be dominated by repeated daily
crypto markets — plausibly **a handful of market families sampled repeatedly**,
not 100 independent questions.

That breaks the A/B in two ways at once:
- **Effective sample size ≪ 100.** Consecutive daily bitcoin markets on one asset
  are serially correlated. Brier over them estimates skill on *one repeated
  question*.
- **External validity ≈ 0 for the deployed use case.** A model selected on daily
  crypto thresholds tells you nothing about NBA or FIFA, which is what the
  feature set is built for.

**Checks before trusting the A/B:**
- Report the **category histogram of the 100 scored outcomes** next to the Brier.
  If any single category exceeds ~40%, say so in the verdict line.
- Report **distinct market families** (normalize slugs — strip dates/strikes:
  `pm-bitcoin-above-{K}-on-{date}` → `pm-bitcoin-above`). If distinct families
  < ~20, the effective n is far below 100 → **do not declare a winner**.
- Report the **horizon distribution** (`close_at − locked_at`). If ~all rows are
  ~24h, the A/B measures only short-horizon skill.
- **Stratify**: report Brier per category, not just pooled. A pooled Brier over a
  74/26 non-sports/sports split with sports-only features is close to
  meaningless.

## C-3. Bridge eligibility skew (structural, by design)

The bridge only registers markets with a **venue-sourced future `close_at`** that
the venue adapter can currently re-read (V33 B2'a). That is the right safety
rule, and it is also a **selection effect**: markets with clean metadata and live
venue availability are over-represented; anything delisted, disputed, or
missing a close time never enters the population at all.

`[measured]` `kalshi_open_events: imported=0, skipped=200` in the V33 local
evidence run, and prod catalog is 694 polymarket / 24 kalshi / 22 seed. **The
accrued set is effectively Polymarket-only.** Any conclusion is a conclusion
about Polymarket.

**Check:** report the venue histogram. If kalshi ≈ 0, state "Polymarket-only" in
the verdict rather than implying venue generality.

## C-4. Horizon skew — and why widening it does NOT help `[analysis]`

`[measured]` the 24h horizon excludes **22 of 25** bridged markets (88%) in prod;
locally it was 11 of 25 (44%). It is the binding filter, as V33 B2 predicted.

**This revises my own V33 F4 framing, and the correction matters.** In V33 I
called the horizon an accuracy-vs-coverage trade. Re-examined against prod data,
**there is no coverage trade at all**:

> Every market passes *through* the 24h window on its way to close. A market
> closing in 30 days is outside the horizon today and inside it on day 29 —
> autolock (every 900s, capacity 2400/day vs. an inflow of a few dozen) will lock
> it then. **The horizon does not decide *whether* a market is locked; it decides
> *when*.**

Since a later lock is a **better-informed** lock, widening the horizon buys
nothing and costs Brier. **Recommendation: do NOT widen `EXTERNAL_AUTOLOCK_WINDOW_SEC`.
F4 should be closed as "measured, rejected — no coverage gain available", not
implemented.**

The one genuine exception: if `eligible` exceeds the batch cap for sustained
periods (§A-1.2), markets could age out unlocked. That is a **batch/frequency**
problem, not a horizon problem, and the fix is the batch cap.

**Check:** before any horizon change, prove the coverage claim empirically —
count markets that closed while never having been locked. If that count is 0,
the horizon is not costing coverage and the argument is closed.

## C-5. Provisional / CLV-gated forecasts

`[measured]` autolock records `model_provisional` and `clv_gate_passed` on every
locked forecast (`forecast_autolock.py:154-155`). V33's local evidence used
`provisional=True, clv_gate_passed=False`.

If a large share of the 100 are provisional or CLV-gate-failing, they are
forecasts the system itself does not fully trust — grading them as if they were
first-class inflates or deflates Brier for reasons unrelated to model skill.

**Check:** report the provisional / `clv_gate_passed` split of the 100, and
report Brier with and without provisional rows.

## C-6. Survivorship via VOID / non-terminal resolutions

`external_resolve` only settles on an **unambiguous terminal** venue outcome;
VOID / disputed / 50-50 markets stay OPEN and never score
(`external_market_resolver.py`, V14). Correct — and it means the scored
population **systematically excludes ambiguous markets**, which are plausibly the
*hard* ones.

**Check:** count bridged markets that closed but never resolved. If that set is
large relative to 100, the Brier is measured on an easy subset and should be
reported as such.

## C-7. Single-forecaster / single-model provenance

Every autolocked forecast comes from one forecaster id and whatever
`ML_MODEL_TYPE` was deployed **at lock time**. If the default model changes
mid-accrual, the 100 rows are a **mixture of two models' predictions** with no
column recording which produced them.

**Check:** before the A/B, confirm `ML_MODEL_TYPE` was constant across the
accrual window (`[measured]` `model_default: xgboost` today). If it changed,
partition by lock time or discard the pre-change rows. Consider filing a ticket
to record the producing model version on each locked forecast — cheap now,
impossible retroactively.

---

# Recommended V40 exit criteria

The accuracy loop is **ready** when all of these hold — not when
`resolved_count` hits 100:

1. `source == "forecast_scores"` and `forecast_scored_count >= 100` (§B-2).
2. `lightgbm_available == true` in the prod image, **or** the A/B is run offline
   somewhere it is available (§B-4).
3. The gate/dataset population question (§C-1) is **resolved by decision**, and
   `len(df) >= 100` is asserted independently.
4. The 100 pass the concentration checks (§C-2): no category > ~40%, distinct
   market families ≥ ~20, horizon distribution reported.
5. `ML_MODEL_TYPE` constant across the accrual window (§C-7).

If 1–2 hold but 3–4 do not, the honest action is E06's: **run it, report both
Briers, declare no winner, and say exactly why.** That is a successful loop
outcome, not a failed one.
