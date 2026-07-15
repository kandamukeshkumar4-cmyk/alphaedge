# loop-v33-lockbreadth — STATE

## LOOP LOG

### B1 — Autolock eligibility funnel audit · DONE (verifier: PASS)

**Verdict: the funnel is INPUT-STARVED at stage 0. None of the five filters
named in GOAL.md (open → close_at → horizon → lacks-LIVE → batch cap) is the
binding constraint, because the worker never sees a single candidate row.**

#### Instrument

`backend/scripts/autolock_funnel_snapshot.py` (new, read-only — SELECTs only).
It runs the exact filter chain from `app/workers/forecast_autolock.py` as staged
counts. It deliberately starts at **stage 0 = total rows in `external_markets`**,
because a starved input set is invisible if you begin the funnel at `status == OPEN`.

#### Local snapshot — REAL numbers, real code path, real upstream APIs

Repro: `goals/loop-v33-lockbreadth/evidence/local_funnel_run.py` (fresh SQLite →
real live-ingest → snapshot). Measured 2026-07-15T17:36:00Z:

```
REAL INGEST (real Kalshi + Polymarket APIs):
  kalshi_open_events    imported=0   updated=0  skipped=200
  polymarket_curated    imported=99  updated=0  skipped=4

AUTOLOCK FUNNEL (params: limit=25, window_sec=86400):
  0_external_markets_total   0
  1_status_open              0
  2_has_close_at             0
  3_close_at_in_future       0
  4_within_horizon           0
  5_lacks_live_forecast      0
  6_after_batch_cap          0

  input_starved:      true
  biggest_exclusion:  INPUT_STARVED — external_markets is empty; no filter can
                      be the binding constraint because the worker sees no rows.
  context.catalog_markets_total: 99
```

**99 real open markets ingested → 0 autolock candidates.** The exclusion is 100%
at stage 0, before any filter GOAL.md asked me to measure.

#### Prod READ-ONLY API counts (https://alphaedge-api-production-b9db.up.railway.app)

Measured 2026-07-15 ~17:30–17:36Z, GETs only:

| Endpoint | Real value |
|---|---|
| `/health` | `status=ok`, `paper_trading_only=true` |
| `/api/v1/system/resolved-count` | `resolved_count=1`, `ab_threshold=100`, `ab_ready=false` |
| `/api/v1/markets?limit=500` | **721 catalog markets** — open=377, locked=198, resolved=146 |
| `/api/v1/backfill/markets` (RESOLVED `external_markets`) | **0** |
| `/api/v1/eval/evaluations` | `[]` |
| `/api/v1/eval/aggregates` | `market_count=0` |
| `/api/v1/clv-track-record` | `records: []` |
| `/api/v1/system/loops` → `forecast_autolock` | `running=true, status=ok`, hb `2026-07-15T17:16:31Z`, `interval_sec=900` |

The autolock loop **is alive and passing every 900s in prod** — it is not disabled,
not crashed, not misconfigured. It simply has nothing to select.

Note on `resolved_count=1`: `count_resolved_outcomes` (`app/ml/ab_harness.py:43`)
falls back to `_from_paper_orders` when there are **no** resolved forecast rows.
With `backfill/markets=0`, `eval/evaluations=[]` and `clv-track-record` empty,
that `1` is almost certainly the paper-orders fallback — i.e. the forecast-scored
count is plausibly **0**. Corroborates the local snapshot; not asserted as fact
(prod DB is not reachable read-only from here — see BLOCKED note).

#### Root cause (code path, greppable)

1. `external_markets` has exactly **one** writer: `ExternalMarketService.resolve_url*`
   (`app/services/external_market_service.py:73`).
2. That writer is reachable from exactly **two** callers, both forecaster-driven:
   `POST /api/v1/markets/external/resolve-url` (`app/api/v1/forecast_routes.py:109`)
   and `POST /api/v1/forecasts` (`app/api/v1/forecast_routes.py:126`).
3. The live-ingest loop — which supplies all 721 prod / 99 local markets — writes
   **only** the `Market` catalog table: `live_market_ingest.py:205` and
   `kalshi_live_ingest.py:242`. **Neither ever constructs an `ExternalMarket`.**
   The two tables are disconnected; autolock reads the one ingest never fills.
4. Self-exclusion of the few rows that do exist: `POST /forecasts` creates the
   `ExternalMarket` *and* locks its forecast in the same request
   (`forecast_routes.py:126-148`). With `mode=LIVE` the row is born already
   excluded by filter 5 (`~live_forecast_exists`). The only row that can ever be a
   candidate is one registered via `resolve-url` **without** a follow-up forecast —
   and no automated caller does that.

#### Which filter excludes the most?

**None of them.** Ranked by markets actually excluded, measured:

| Stage | Excluded (local, real) |
|---|---|
| **0 — row never created in `external_markets`** | **99 of 99 (100%)** |
| 1 status open | 0 |
| 2 has close_at | 0 |
| 3 close_at in future | 0 |
| 4 within horizon | 0 |
| 5 lacks LIVE forecast | 0 |
| 6 batch cap | 0 |

#### Consequence for B2 (config tuning)

Horizon, batch size, and pass frequency all multiply a candidate set of size **0**.
Widening the horizon 24h → 7d yields 7 × 0 = 0. **No config change can move
resolved_count**, so B1's data cannot justify one. Recorded honestly in B2 rather
than shipping a cosmetic tune. The real fix is a catalog→external supply bridge,
which is new ingest code, not config → **FILED in B2** per GOAL B2 + DIR-V33-001.3.

#### BLOCKED-ON-ENV (does not block B1's verdict)

- Prod DB not snapshot-able from here: no read-only prod `DATABASE_URL`; the
  autolock `JobRun` summary (`candidates`/`locked`/`skipped`/`errors`) is only
  exposed via `/api/v1/admin/jobs`, which needs the prod `ADMIN_API_KEY` I do not
  have and will not guess. `/api/v1/system/loops` exposes liveness but not the
  summary counts. **Ask:** run
  `uv run --extra dev python scripts/autolock_funnel_snapshot.py` against prod
  `DATABASE_URL` (read-only) to confirm stage 0 = ~0 in prod, or expose the JobRun
  summary in `/api/v1/system/loops`.
- Local `alphaedge` Postgres not available (`localhost:5432` open but rejects
  `alphaedge/alphaedge`), so the local snapshot uses a throwaway SQLite DB filled
  by the real ingest path — which is the stronger measurement anyway: it proves
  ingest produces 0 external markets from 99 real live ones.

#### Gate (B1)

Instrument is read-only and additive; no app code touched.
`ruff check app tests scripts` → PASS. Full pytest counts run under B3.

AutoLab: baseline=funnel unmeasured | benchmark=scripts/autolock_funnel_snapshot.py stage counts | iterations=1 (stage-0 starvation identified + reproduced) | budget=1/3 | outcome=improved (root cause located; config path falsified)

---

### B2 — Config tuning · DONE (no config change is justified; findings FILED)

**Verdict: I am shipping ZERO config changes, and that is the finding.**
B1 measured every funnel stage at 0 because the input set is empty. Horizon,
batch, and frequency are all multipliers on a candidate set of size 0
(24h → 7d = 7 × 0 = 0). DIR-V33-001.2 requires real numbers; the real numbers
justify no tune. Shipping one would be cosmetic — motion that looks like
progress and moves `resolved_count` by exactly nothing.

#### Every filter considered, individually

| Filter (`forecast_autolock.py:108-112`) | Widen? | Why |
|---|---|---|
| `status == OPEN` | **No** | A locked/resolved market cannot take a pre-close forecast. Not a restriction, a definition. |
| `close_at IS NOT NULL` | **Never** | Widening = locking a market whose close time is unknown, i.e. unprovable pre-close. This filter *is* the pre-close guarantee. SACRED. |
| `close_at > now` | **Never** | Widening = locking at/after close. SACRED — automatic incident per DIR-V33-001.1. |
| `close_at <= horizon` | **Tunable, but not justified** | The only genuinely tunable filter. Multiplies 0. See cost below. |
| `~live_forecast_exists` | **No** | Widening = multiple locks per market, letting the track record cherry-pick its best entry. Directly corrupts the trust output. |
| batch cap (`limit=25`) | **No** | Never reached: 0 candidates ≪ 25. Non-binding. |
| pass frequency (900s) | **No** | The loop already runs and passes in prod (`system/loops` hb, B1). Running a query that selects 0 rows more often selects 0 rows more often. |

So of the seven knobs, six are load-bearing for safety or non-binding, and the
seventh multiplies zero.

#### Why the horizon tune is not a free hedge

Widening the horizon is *safe* (it cannot cause an at/after-close lock —
`close_at > now` plus the in-flight re-check at `forecast_autolock.py:172-181`
still bind). But it is not free: locking 7 days out instead of 24h out means
forecasting with less information, which is a real accuracy cost on a track
record whose whole value is trust. Paying an accuracy cost for a coverage gain
of provably zero is a bad trade — and once F1 lands, the right horizon should be
chosen against *measured* stage-3→4 drop, not guessed now.

**Honest caveat (does not change the verdict):** stage 0 = 0 is measured
*locally*. Prod's `external_markets` count is not directly observable (F2), so I
cannot rule out that prod holds a handful of forecaster-submitted rows sitting
just outside a 24h horizon. Prod evidence is strong but indirect
(`backfill/markets=0`, `eval/evaluations=[]`, `eval/aggregates.market_count=0`,
`clv-track-record` empty). If F2's prod snapshot shows real rows dropping at
stage 3→4, a horizon tune becomes data-justified and should be its own ticket.
Tuning now, on inference, is exactly what DIR-V33-001.2 forbids.

#### Filed, not implemented → `goals/loop-v33-lockbreadth/FINDINGS.md`

- **F1** — catalog→external supply bridge. The only change that can lift stage 0
  above zero, therefore the only one that can move `resolved_count`. New ingest
  code, not config → out of B2 scope by GOAL B2 + DIR-V33-001.3. Filed with its
  safety constraints (venue-sourced `close_at` only; exact venue identity or the
  resolver scores the wrong market; never write `winning_outcome`; idempotent;
  bounded).
- **F2** — prod autolock funnel unobservable; blocks data-justified tuning. Ask:
  read-only prod snapshot, or surface the JobRun summary in `/api/v1/system/loops`.
- **F3** — `resolved_count` silently falls back to paper orders
  (`ab_harness.py:43-52`), so the A/B gate's "1 of 100" may measure a different
  population than this loop accrues. Ask: label the source.

#### Gate (B2)

No runtime code touched (docs only). `ruff check app tests scripts` → PASS.
Full pytest counts under B3.

AutoLab: baseline=0 autolock candidates (B1) | benchmark=stage-0 candidate count | iterations=1 (evaluated all 7 knobs; 0 justified) | budget=2/3 | outcome=stalled-reorganized (config axis is provably a no-op; real fix reorganized into F1 for its own ticket)
