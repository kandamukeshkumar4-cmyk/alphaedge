# SCOUT105-PROVENANCE

Read-only terrain map for the alpha factor provenance / closing-line gap.
Evidence cited as `path:line`. INFERRED labels mean derived from code structure, not a runtime observation.

---

## 1. Validator's required input shape (exact)

### Population source (outer join set)

`load_factor_observations` loads the scored LIVE forecast population, then re-reads `ForecastLog` rows by id:

- Population: `load_forecast_score_rows(session)` — `backend/app/ml/forecast_ab_dataset.py:52-100`
  - Join: `ForecastScore` ⋈ `ForecastLog` ⋈ `ExternalMarket`
  - Filters: `ForecastLog.mode == LIVE`, `ExternalMarket.status == RESOLVED`, `winning_outcome IS NOT NULL` (`:62-66`)
  - Row keys used later: `forecast_id`, `actual_outcome`, `locked_at`, `correlation_cluster` (`:74-89`, consumed at `validator.py:79-112`)

- Lock re-read: `select(ForecastLog.id, user_probability, market_implied_probability, time_to_resolution_seconds, snapshot_metadata).where(id.in_(ids))` — `backend/app/alpha/validator.py:67-75`

### Per-row required shape

| Field | Source | Type constraint |
| --- | --- | --- |
| `forecast_id` | `ForecastLog.id` / population | UUID string |
| `user_probability` | `ForecastLog.user_probability` | float in `[0,1]` via `_probability` (`:276-285`) → injected as `model_probability` |
| `market_implied_probability` | column **or** features | float in `[0,1]`; required as **entry** (`:89-93`) |
| `time_to_resolution_seconds` | column | optional int → `hours_to_lock = seconds/3600` (`:193-195`) |
| `snapshot_metadata.closing_implied_probability` | JSON key | float in `[0,1]`; required as **closing** (`:90-96`) |
| `snapshot_metadata.alpha_features` | JSON object | optional dict; factor-specific keys (`:184-187`) |
| `actual_outcome` | `ForecastScore.actual_outcome` | int 0/1 (`:108`) |
| `locked_at` | population | datetime (`:109`) |
| `correlation_cluster` | population | string (`:101,111`) |

`_lock_features` always overwrites/injects from columns (`:184-196`):

```
features = dict(snapshot_metadata["alpha_features"] or {})
features["model_probability"] = user_probability
features["market_implied_probability"] = market_implied_probability
features["edge"] = model - market  # or None
features["hours_to_lock"] = time_to_resolution_seconds / 3600  # or None
```

### Factor-specific keys inside `alpha_features` (after injection)

From `backend/app/alpha/factors.py`:

| Factor | Required keys | Fail reason if missing |
| --- | --- | --- |
| `model_edge` | `model_probability`, `market_implied_probability` | `missing_model_or_market_probability` (`:16-22`) |
| `whale_flow` | `whale_flow` (number) | `missing_whale_flow` (`:25-30`) |
| `momentum` | `price_history` seq of ≥2 probs | `missing_price_history` (`:33-38`) |
| `mean_reversion` | `price_history` seq of ≥2 probs | `missing_price_history` (`:41-47`) |
| `news_sentiment` | `news_signal`, `sentiment_debate` | `missing_news_or_debate_sentiment` (`:50-56`) |
| `time_decay` | `hours_to_lock`, `edge` | `missing_hours_to_lock_or_edge` (`:59-65`) |
| `cross_venue` | `polymarket_probability`, `kalshi_probability` | `missing_mirrored_venue_probability` (`:68-74`) |

Factor returns `provenance.available` True/False (`:88-101`).

### Kill counters — exact branch points

```
# backend/app/alpha/validator.py:79-100
if forecast is None:
    missing["missing_factor_provenance"] += 1
elif not FACTOR_FUNCTIONS[factor](features)["provenance"]["available"]:
    missing["missing_factor_provenance"] += 1
elif entry (market_implied) is None:
    missing["missing_factor_provenance"] += 1
elif closing (snapshot_metadata["closing_implied_probability"]) is None:
    missing["missing_closing_line"] += 1
elif score not finite:
    missing["missing_factor_provenance"] += 1
```

Empty observation set → reject reason (`:136-142`):

```
"missing_closing_line" if missing_closing_line > 0 else "insufficient_factor_provenance"
```

Note: API reason `missing_locked_forecast` is **not** from the validator. It is from `AlphaService._current_factors` when no `ForecastLog` exists for the market (`backend/app/alpha/alpha_service.py:74-76`). That powers `GET /api/v1/alpha/factors` (`backend/app/api/v1/alpha.py:22-27`).

### Writer proof for keys the validator reads

Repo-wide production writers of these metadata keys:

- `alpha_features`: **readers only** in app code — `validator.py:186`, `alpha_service.py:78`, `regime_auditor.py:59`. Grep for assignment finds **no app writer**. Test-only write: `tests/test_alpha_validator.py:85`, `tests/test_alpha_service.py:28`.
- `closing_implied_probability`: **reader only** in app — `validator.py:90`. Test-only write: `tests/test_alpha_validator.py:85`. Mentioned in `STATE96.md:43`.

`snapshot_metadata` itself is written at lock as a passthrough dict (`forecast_service.py:177,227`; autolock keys at `forecast_autolock.py:150-159` — `lock_origin`, `model_provisional`, `clv_gate_passed`, `selected_at`, `selection_window_sec` + adapter metadata). **Neither alpha key is set there.**

---

## 2. Forecast production path + recommended hook point (file:line)

### Production path (model autolock — primary LIVE locks)

1. Scheduler: `_forecast_autolock_loop` → `forecast_autolock_task` — `backend/app/main.py:600-611`, ARQ `cron(..., minute={0,30})` — `workers/tasks.py:1321`
2. Batch: `autolock_forecasts` — `workers/forecast_autolock.py:80`
3. Probability: `ForecastService.predict(external_id, implied_yes=...)` — `:140-146` → `predict_market` — `services/forecast_service.py:93-117` → `forecasting/predictor.py:60`
4. **Final persist (natural hook):** `service.lock_forecast(...)` — `forecast_autolock.py:161-175` → `ForecastService.lock_forecast` — `services/forecast_service.py:140-252`
   - INSERT `MarketSnapshot` (`:190-199`)
   - INSERT `ForecastLog` with `snapshot_metadata=effective_metadata`, provenance columns (`:206-239`)
   - Emit domain event `forecast_locked` (`:241-251`)

### Secondary lock path (human / extension)

- `POST /forecasts` → `ForecastService.lock_forecast` — `api/v1/forecast_routes.py:117-147`
- Accepts client `body.snapshot_metadata` as-is (`:145`); no server-side alpha enrichment.

### Predictor finalization (not persistence)

- `predict_market` returns `ForecastPrediction` with `predicted_prob`, gates, `producer` — `forecasting/predictor.py:140-153`
- Autolock stores `prediction.model_prob` as `user_probability` and `prediction.provenance` on columns (`forecast_autolock.py:164,174`)

### Hook-point notes (map only, not a design)

| When | What fits | Evidence |
| --- | --- | --- |
| Lock time | Snapshot `alpha_features` into `ForecastLog.snapshot_metadata` (and twin `MarketSnapshot.metadata`) | Single INSERT site: `forecast_service.py:206-227`; autolock is the prod caller that builds metadata (`forecast_autolock.py:150-169`) |
| Close / resolve time | `closing_implied_probability` cannot be true at lock; scoring path today only inserts `ForecastScore` | `scoring_service.py:85-94` — **no** metadata update |

INFERRED: true closing line must be a **post-lock** write (or a parallel table keyed by `forecast_id` / `external_market_id`), because lock intentionally runs while `close_at > now` (`forecast_autolock.py:109-111,179-184`).

---

## 3. Lock mechanism — who sets it, or proof nobody does

### What `"locked": false` means

`GET /api/v1/markets/{slug}/locked-forecast` — `api/v1/market_locked_forecast.py:188-230`

- There is **no** `locked` column on markets.
- `locked=True` iff a LIVE `ForecastLog` exists for the resolved `ExternalMarket` (`:205-219`).
- Else `_empty_response(..., locked=False, empty_reason="pre_lock")` (`:166-185,202-211`).

Lookup order: prefer autolock system forecaster `AUTOLOCK_FORECASTER_ID`, else any LIVE row (`:121-148`).

### What sets lock true

**Only** inserting a LIVE `ForecastLog` via `ForecastService.lock_forecast` (`services/forecast_service.py:140-252`).

### Every production caller of `lock_forecast` found

| Caller | Path | Lines |
| --- | --- | --- |
| Autolock worker | `workers/forecast_autolock.py` | `161-175` |
| Forecast API | `api/v1/forecast_routes.py` `create_forecast` | `136-147` |

Grep of `lock_forecast(` under `backend/app` returns only those two call sites (+ definition).

### What does **not** set lock

- Alpha daily run: validates only; writes `alpha_runs` (`alpha_run_service.py:83-92`)
- Scoring: writes `forecast_scores` only (`scoring_service.py:85-94`)
- `predict_market` / `ForecastService.predict`: in-memory, no DB lock
- Closing-snapshot admin/worker: odds ingest, not ForecastLog

If prod returns `locked:false` for a slug: either no `ExternalMarket` match (`:202-203`) or no LIVE `ForecastLog` (`:206-211`) — not a separate flag stuck false.

---

## 4. Closing line — where it could come from

### What the alpha validator wants (exact key)

`ForecastLog.snapshot_metadata["closing_implied_probability"]` — `validator.py:90`

**No production writer** of that key exists (see §1).

### Places closing-ish values exist or can be computed

| Location | What | Written to DB? | Usable as alpha closing? |
| --- | --- | --- | --- |
| `odds_snapshots` | Time series `implied_yes` / `price`, optional `close_at` | Yes — ingest path | Last pre-close snapshot: `eval/service.py:62-81` (`_closing_implied` over catalog `Market.slug`) |
| `ml/features.py` | Offline CSV/frame `closing_implied` = last eligible pre-close `implied_yes` | Training frames | `:125-167` — not ForecastLog |
| `evaluations.closing_implied` | Catalog eval path | Yes when `EvalService.evaluate_market` runs | `models.py:637`; `eval/service.py:41-50` — different market identity (`markets` not `external_markets`) |
| `market_snapshots.implied_probability` | Venue implied **at lock** | Yes at lock | Entry line, not close (`forecast_service.py:190-197`) |
| `ForecastLog.market_implied_probability` | Same as entry | Yes at lock | Entry, not close |
| `backtesting/clv.py` | Pure math: needs caller-supplied `closing_implied` / `closing_yes` | No | `:60-65,149-163` |
| `portfolio_clv.py` / `CLVTrackingService` | CLV from `signal_events` payload tracking | Signal events only | `forecast_dashboard_service.py:93-114,505-522` — not ForecastLog |
| `pipeline/ingest.py` `capture_configured_historical_closing_snapshots` | Odds-API historical h2h → `odds_snapshots` | Yes | `:164-201` — not ForecastLog metadata |
| `ScoringService.score_market` | Outcome + Brier only | `forecast_scores` | **Does not** capture market close price (`scoring_service.py:75-94`) |
| `resolved.py` | `model_p_at_close` = latest LIVE **user_probability** | Read-only API | `:67-68,130` — model p, not market closing line |

### Bottom line

A **market final pre-resolution price** can exist unbundled in `odds_snapshots` (and catalog `evaluations`), but the alpha path’s required field on `forecast_logs.snapshot_metadata` is **never populated** by any worker/endpoint/scorer found.

---

## 5. Existing tables + current alembic head

### Tables relevant to forecast / resolution / factor inputs

| Table | Model lines | Holds | Provenance carrier? |
| --- | --- | --- | --- |
| `forecast_logs` | `models.py:1312-1393` | Locked p, entry implied, `snapshot_metadata` JSON, V56 provenance cols | **Primary**: already has JSON + nullable provenance cols (`048_lock_provenance.py`). Can carry `alpha_features` / `closing_implied_probability` without schema change. |
| `market_snapshots` | `1289-1309` | Lock-time venue snapshot + `metadata` JSON | Twin of lock metadata; same JSON pattern. |
| `forecast_scores` | `1463-1481` | `actual_outcome`, Briers | Outcome label only; no closing / factors. |
| `external_markets` | `1260-1286` | status, `close_at`, `resolved_at`, `winning_outcome` | Identity + resolution bounds. |
| `odds_snapshots` | `496-521` | Price history / implied time series | Source to **derive** closing or `price_history`; different slug keyspace than `external_id`. |
| `prediction_logs` | `604-625` | Catalog model predictions | Parallel ledger; not alpha population. |
| `evaluations` | `629-639` | Catalog Brier + `closing_implied` | Catalog only. |
| `whale_events` | `816-837` | Large trades + `captured_at` | Can recompute pressure **if** policy allows recompute (see §6). |
| `market_sentiment_snapshots` | `840-860` | `sentiment_score`, `volume_score`, `captured_at` | Partial news-side history; not both `news_signal`+`sentiment_debate`. |
| `venue_gaps` | `863-893` | PM/KS implied + gap | Cross-venue raw levels at capture time. |
| `venue_market_matches` | `681-703` | PM↔KS pairing | Needed to join venues. |
| `alpha_runs` | `1484-1498` | Daily research result JSON | Downstream of validation; not factor inputs. |
| `feature_snapshots` | `524-531` | Generic feature JSON by market_slug | Unused by alpha validator. |
| `signal_events` | `665-678` | Paper signals + payload | CLV track record path. |
| `market_resolutions` | `256-262` | Catalog slug → outcome | Catalog resolution. |
| `forecast_drift_snapshots` | `1570-1595` | Rolling Brier/ECE | Aggregate only. |

### New table warranted?

- **Not required** for the two missing keys if implementer is willing to mutate/extend `forecast_logs.snapshot_metadata` (and optionally update immutability policy for a close-time patch).
- **Warranted** if close-time values must not rewrite lock-time JSON (append-only invariant): a small `forecast_closing_lines(forecast_id, closing_implied, captured_at, source)` or extend `forecast_scores` with `closing_implied`. Map only — decision is implementer’s.

### Current alembic head

- Linear tip of the main chain: **`064_alpha_runs`** — `alembic/versions/064_alpha_runs.py:14-15` (`down_revision = "063_marketplace_ratings"`).
- Merge earlier in chain: `018_wc2026_tag` merges dual `017_user_onboarding` + `017_position_settled` (`018_wc2026_tag.py:14-17`).
- File count under `alembic/versions/`: 63 `.py` files; no `044_*` file (043 → 045 numbering gap).
- Head detection via revision graph: tip `064_alpha_runs` (the only head after the 017 merge is consumed by 018).

---

## 6. Reconstructible vs lost-forever, per factor (table)

Conservative rule: if reconstruction requires assuming window, settings, cache state, or identity mapping not recorded on the lock row → **NOT reconstructible**.

| Factor | Required lock-time inputs | Stored today without `alpha_features`? | Verdict |
| --- | --- | --- | --- |
| `model_edge` | `model_probability`, `market_implied_probability` | Yes: `ForecastLog.user_probability`, `market_implied_probability` — validator injects (`validator.py:188-192`) | **RECONSTRUCTIBLE** from columns (still blocked by missing **closing** for OOS gate) |
| `time_decay` | `hours_to_lock`, `edge` | Yes: `time_to_resolution_seconds` + model−market edge injection (`:193-195,192`) | **RECONSTRUCTIBLE** from columns (same closing gate) |
| `whale_flow` | scalar `whale_flow` | Raw `whale_events` exist (`models.py:816-837`); pressure is process-cache + recompute (`whale_flow.py:64-76,248+`; `whale_flow_service.py:171+`). Factor key is `whale_flow`, graph uses `whale_pressure` (`agents/graph.py:152-154`) — name mismatch; no lock-time scalar stored | **NOT reconstructible** as the historical lock-time feature (would assume window/settings/slug mapping) |
| `momentum` | `price_history` sequence | `odds_snapshots` may hold series, but **window definition never recorded** on the lock; autolock does not write `price_history` | **NOT reconstructible** |
| `mean_reversion` | same `price_history` | same | **NOT reconstructible** |
| `news_sentiment` | `news_signal` + `sentiment_debate` numbers | News is **in-memory TTL cache only** (`news_signal.py:11-12,50-69`). Debate rows → unstructured `analyst_briefs` (`sentiment_debate.py:130-146`), not a numeric pair on the lock. `market_sentiment_snapshots` has one score stream only | **NOT reconstructible** (gone if never snapshotted) |
| `cross_venue` | `polymarket_probability`, `kalshi_probability` | `venue_gaps` / `venue_market_matches` hold latest-ish levels, not lock-time pair bound to `forecast_id` | **NOT reconstructible** without assuming “nearest gap row == lock features” |

### Closing line for all factors

| Artifact | Reconstructible? |
| --- | --- |
| `snapshot_metadata.closing_implied_probability` on historical `forecast_logs` | **Not present.** May be **derivable** from `odds_snapshots` last pre-close for a mapped slug (`eval/service.py:62-74`) — that is a **new policy**, not recovery of a written value. Requires identity map `external_id` ↔ `market_slug` / `pm-` prefix (`market_locked_forecast.py:52-75`). Any gap in snapshots → unrecoverable for that market. |
| Entry implied at lock | **Yes** — `ForecastLog.market_implied_probability` / `market_snapshots` |

### Backfill implication

- Honest backfill of full 7-factor OOS set: **no** — 5/7 factors lost without lock-time capture.
- Partial: `model_edge` + `time_decay` scores can be replayed from existing columns; still need a **defined** closing-line backfill policy (odds last pre-close) to leave `missing_closing_line`.

---

## 7. Scheduler wiring notes

### Alpha daily run (consumer of provenance — does not create it)

| Wire | Location |
| --- | --- |
| In-process loop | `main.py:342-367` `_alpha_model_loop` |
| Flag | `settings.scheduler_alpha_model_enabled` default True — `config.py:98-100`; started `main.py:816-817` |
| Schedule | Boot: immediate catch-up once (`:351-356`); then sleep until next **07:00 UTC** (`:359-360`) |
| ARQ mirror | `cron(alpha_model_task, hour={7}, minute={0})` — `workers/tasks.py:1335` |
| Task | `alpha_model_task` → `run_alpha_model_task` — `tasks.py:998-1002`, `alpha_run_service.py:208-216` |
| Body | `AlphaRunService.run_daily` → `validate_all_factors` → optional regime/constructor/decomposer → INSERT `alpha_runs` (`:26-92`) |
| Idempotency | One row per `run_date`; reuse if exists (`:28-30`) |
| Order path | Explicitly research-only; no orders (`alpha_run_service.py:21,209`) |

### Related writers the fixer must not confuse with alpha

| Loop | Role | Lines |
| --- | --- | --- |
| `_forecast_autolock_loop` | **Creates** LIVE locks (hook for `alpha_features`) | `main.py:600-624,838-839`; cron `tasks.py:1321` |
| External resolve + scoring | Resolves markets → `ForecastScore` (hook candidate for closing) | `scheduler_external_resolve_enabled` `config.py:112-114`; scoring `scoring_service.py:32-94` |
| Whale / venue / news | Populate side tables / caches, **not** forecast metadata | `main.py:824-827`; news cron `tasks.py:1303` |

### Fixer wiring constraints

1. Alpha loop at 07:00 only **reads** lock metadata; writing provenance in `run_daily` is the wrong lifecycle (markets already resolved; lock-time features already missed).
2. Autolock is the LIVE lock INSERT path; any lock-time feature snapshot must land in `lock_forecast` metadata (or columns) on that path.
3. Closing line is available only near close/resolve — not inside autolock eligibility window by definition (`close_at > now`).
4. Dual schedulers (uvicorn in-process + ARQ cron) both call the same tasks; writes must be idempotent (autolock already uses `idempotency_key=f"model-autolock:{market.id}"` — `forecast_autolock.py:170`).
5. Alpha router is registered: `main.py:55,1082`.

---

## Open questions the implementer must decide

1. **Close-time mutation policy:** May `forecast_logs.snapshot_metadata` be updated after lock to add `closing_implied_probability`, or must a new append-only table/column be used?
2. **Closing definition:** Last `odds_snapshots` pre-`close_at`? Last venue adapter fetch before resolve? Midpoint of bid/ask? Document must match `clv-model-gate` honesty rules.
3. **Identity bridge:** How to map `ExternalMarket.external_id` / platform to `odds_snapshots.market_slug` (`pm-` / `ks-` / raw) for backfill and live close capture.
4. **Which factors ship first:** Only reconstructible pair (`model_edge`, `time_decay`) vs full 7 — full set requires lock-time capture of whale/price/news/venue features that are currently never written.
5. **`whale_flow` vs `whale_pressure`:** Factor key is `whale_flow` (`factors.py:27`); graph/cache use `whale_pressure` (`agents/graph.py:154`). Which scalar is the contract?
6. **`price_history` contract:** Length, sampling interval, source (`odds_snapshots` vs venue), and whether to store the array or enough to recompute.
7. **Backfill ethics:** Is odds-derived closing acceptable for pre-existing rows, or must OOS only include rows after write path ships (V56-style no-backfill for provenance)?
8. **Human locks:** Should `POST /forecasts` also stamp `alpha_features`, or only system autolock?
9. **Regime auditor extras:** Also needs `volume` + category for regime rows (`regime_auditor.py:59-68`) — adjacent gap if regimes are in scope.
10. **Alembic:** Prefer JSON-only fix (no migration) vs typed columns on `forecast_logs` / new table; head is `064_alpha_runs`.

---

## Evidence index (quick)

| Claim | Cite |
| --- | --- |
| Validator reads closing + alpha_features | `backend/app/alpha/validator.py:84-96,184-196` |
| Kill reason preference when empty | `validator.py:136-142` |
| Factors pure + keys | `backend/app/alpha/factors.py:16-85` |
| Population = scored LIVE resolved | `backend/app/ml/forecast_ab_dataset.py:52-68` |
| Lock INSERT | `backend/app/services/forecast_service.py:140-252` |
| Autolock caller | `backend/app/workers/forecast_autolock.py:140-175` |
| API lock caller | `backend/app/api/v1/forecast_routes.py:136-147` |
| `locked` derived from ForecastLog | `backend/app/api/v1/market_locked_forecast.py:166-230` |
| No app writer of `closing_implied_probability` / `alpha_features` | grep: only `validator`/`alpha_service`/`regime_auditor` readers + tests |
| Scoring omits closing | `backend/app/services/scoring_service.py:75-94` |
| Odds-based closing exists for catalog eval | `backend/app/eval/service.py:62-81` |
| Alpha scheduler | `backend/app/main.py:342-367,816-817`; `workers/tasks.py:998-1002,1335` |
| Alembic tip | `backend/alembic/versions/064_alpha_runs.py:14-15` |

AutoLab: not applicable (no iterative measure) — scout map only.
)
