# SCOUT110-ARTIFACTS

Read-only terrain map for model artifacts vs the production prediction facade.
Evidence is `path:line` (repo) or **PROD GET** (timestamped 2026-07-25, host
`https://alphaedge-api-production-b9db.up.railway.app`). Claims without either
are labeled **INFERRED** or **UNVERIFIED**.

**Scope:** map only. No source edits, no push/deploy, no prod mutation, no secrets.

**Symptom (confirmed):** prod writes `PredictionLog` rows whose `model_p` ≈
`market_p` → absolute edges ~0 → default opportunities board empty under the
CLV/`signal_only` gate.

---

## 1 Artifact contract (exact)

### 1.1 Entry: `predict_market`

`backend/app/forecasting/predictor.py:60-153`

1. Read implied: `implied_yes` or `market_implied` (default 0.5) (`:66`).
2. If `market_slug` starts with `wc2026-`, call FIFA path; on success
   `producer=PRODUCER_FIFA` (`:69-74`). On failure, fall through.
3. Else/also: `_artifact_probability(features)` (`:76-79`).
   - If not `None` → `producer=PRODUCER_ARTIFACT`, use that float.
4. Else: use first of `model_probability` / `calibrated_probability` /
   `predicted_prob`, else **implied** (`:81-86`).
   - If any of those three keys present → `PRODUCER_SUPPLIED`.
   - Else → **`PRODUCER_IMPLIED_PASSTHROUGH`** (`:30-33`, `:82-86`).
5. CLV / significance / executable edge gates only run when
   `forecast_comparisons` (or `closing_comparisons`) are supplied (`:88-129`).
   Without them: `is_edge=False`, `edge=0.0`, reason
   `"no resolved walk-forward evaluation"` (`:93`, `:131`).

### 1.2 `_artifact_probability` contract

`backend/app/forecasting/predictor.py:249-274`

| Requirement | Exact rule |
| --- | --- |
| Paths | `model_artifact_path` **or** `artifact_path`; calibrator:
  `model_calibrator_path` **or** `calibrator_path` (`:250-253`) |
| Columns | `feature_columns` must be a non-string `Sequence` of names (`:254-262`) |
| All-or-nothing | If **any** of (model path, calibrator path, columns) is set and not all
  three are set → `ValueError` (`:257-260`) |
| If all three absent | returns `None` (passthrough path) (`:255-256`) |
| Row build | for each name in `feature_columns`, `float(features[column])`; missing
  key → `ValueError` (`:264-268`) |
| Model API | `joblib.load(model_path)` then **`model.predict_proba([row])[0][1]`**
  (binary YES class index 1) (`:270-272`) |
| Calibrator API | `joblib.load(calibrator_path)` then
  **`calibrator.predict([raw_probability])[0]`** (1-D probability in → calibrated
  out) (`:271-273`) |
| File format | **joblib** pickles (not raw sklearn dump API; not the FIFA pickle cache) |

**Not** coefficient linear models by contract — any object with
`predict_proba` / calibrator with `predict` works (tests use stubs:
`backend/tests/test_forecast_predictor.py:40-90`).

### 1.3 What the production writers actually pass

**Primary producer of `prediction_logs`:**
`backend/app/services/prediction_writer.py`

- Batch default **50** (`DEFAULT_PREDICTION_BATCH=50` `:52`; config
  `PREDICTION_WRITER_BATCH` default 50 — `config.py:196`).
- For each OPEN market: latest `OddsSnapshot.implied_yes` →
  `ForecastService.predict(slug, implied_yes=implied)` (`:174-183`).
- Never imports Risk/OrderBook (`:28-29`).

**`ForecastService.predict` feature dict (entire payload):**
`backend/app/services/forecast_service.py:97-101`

```text
{
  "market_slug": slug,
  "implied_yes": implied_yes,
  "market_implied": implied_yes,
}
```

Docstring at `:125-130` and provenance at `:36-41` state explicitly: **no
`model_artifact_path`**, registry not consulted, `artifact_digest` always
`None`, stamping `ml_model_type` would be a fabrication.

**Consequence (code fact):** `_artifact_probability` always returns `None` on
this path → non-FIFA markets are **`implied_passthrough`** →
`predicted_prob == implied` → model-vs-market edge ≈ 0 (float rounding only).

Autolock uses the same `ForecastService.predict` for LIVE locks
(`forecast_autolock.py:140-143`).

### 1.4 Feature builders (who defines training columns)

| Builder | Path | Columns / dataset |
| --- | --- | --- |
| NBA/generic trainer matrix | `app/ml/features.py:7-34` `FEATURE_COLUMNS` | Odds-derived + optional NBA Elo/rest/ratings; labels from scores |
| Fixture loader | `features.py:72-82` | CSVs under fixtures dir: `odds_snapshots_sample.csv`, `final_scores_sample.csv`, optional `nba_games_sample.csv`, `nba_team_stats_sample.csv` |
| Prod resolved catalog matrix | `app/ml/snapshot_dataset.py:11-81` | `OddsSnapshot` ⋈ `Market` where `status=RESOLVED` + `winning_outcome` set; NBA context only if snapshot metadata holds `nba_game` / team stats |
| Forecast A/B (lock-time only) | `app/ml/forecast_ab_dataset.py:26-29` | **`market_implied_probability`, `time_to_resolution_hours`** only |
| FIFA match features | `app/data/fifa/features.py:18-43` `FIFA_FEATURE_COLUMNS` | Form / H2H / stage from pre-kickoff history |
| WC2026 XGB bundle | `app/ml/wc2026_model.py:23-37` | Separate 13-feature form set; joblib dict artifact |

**Trainer persist shape** (`app/ml/trainer.py:439-448`):
writes `artifact_dir/xgboost_model.joblib` + `calibrator.joblib` only.
`feature_columns` is returned in the train-result **dict**, not written as a
sidecar file. Caller must re-supply columns at predict time.

**Classifier factory** (`app/ml/model_registry.py:43-58`): default
`XGBClassifier(n_estimators=50, max_depth=3, …)`; optional LightGBM.

**Calibrators** (`app/ml/calibration.py`): identity / Platt (`LogisticRegression`
on logit) / isotonic — selected by `fit_best_calibrator` in trainer
(`trainer.py:428-433`).

### 1.5 FIFA exception (not the generic artifact contract)

- Slug prefix routing only (`predictor.py:69-74`).
- `FifaPredictor` trains or loads **pickle** cache at
  `backend/app/data/fifa/.model_cache.pkl` (`data/fifa/predictor.py:25`,
  `:109-163`), max age 168h (`:28-34`).
- Returns provisional `is_edge=False` always until closing lines exist (`:70-78`).
- Separate bundled `wc2026_model.pkl` used by `app/ml/wc2026_model.py` (joblib
  dict with model + code map) — **not** wired through `_artifact_probability`.

---

## 2 Existing artifacts + trainers

### 2.1 Artifact files on disk (this worktree)

| Path | Role | Notes |
| --- | --- | --- |
| `backend/app/data/fifa/.model_cache.pkl` | FIFA runtime cache | git **modified** (`git status`); local pickle of (model, MC, dfs) |
| `backend/app/data/fifa/wc2026_model.pkl` | WC2026 XGB bundle | **git-tracked** (`git ls-files`); ~3.0 MB |
| `backend/ml_artifacts/admin_phase3_snapshot_store/phase3_snapshot_walk_forward/{xgboost_model,calibrator}.joblib` | Admin phase-3 backtest outputs | gitignored `*.joblib` pattern |
| `backend/backend/ml_artifacts/{xgboost_model,calibrator}.joblib` + `phase3_walk_forward/*` | Accidental nested path from cwd | local only; gitignored |

`.gitignore:30-34` ignores `backend/ml_artifacts/**/*.joblib`.
`backend/.dockerignore:11-13` excludes `ml_artifacts/*.{joblib,pkl,json}` from
image context (bundled FIFA pkl under `app/data/fifa/` is a separate path).

### 2.2 Trainers / scripts that produce artifacts

| Producer | File | Dataset | Outputs | Auto-activate? |
| --- | --- | --- | --- | --- |
| Fixture XGB trainer | `app/ml/trainer.py:46-88` `train_xgboost_model` | fixtures CSVs via `build_feature_matrix` | `xgboost_model.joblib` + `calibrator.joblib` | No |
| Walk-forward trainer | `trainer.py:91-293` | same fixture/matrix | final fit artifacts + walk-forward metrics | No |
| Snapshot retrain worker | `app/workers/model_retrain.py:27-107` | `load_resolved_snapshot_feature_matrix` (catalog `Market`+`OddsSnapshot`) | train dir under `artifacts/retrain/<ts>/`; **registers** `ModelVersion` with `activate=False` | **Never** auto-activates (`:4-5`, `:86`) |
| Backtest CLI | `scripts/run_backtest.py` → `app/backtesting/replay.py:18-22` | fixtures | default `backend/ml_artifacts` | No |
| Admin phase-3 snapshot backtest | `app/admin/routes.py:42-46` + replay | DB snapshot matrix | `ml_artifacts/admin_phase3_snapshot_store/...` | No |
| FIFA predictor boot | `app/data/fifa/predictor.py:108-163` | `intl_results.csv` (+ fixtures/bracket CSVs) | `.model_cache.pkl` | N/A (self-load) |
| WC2026 train helper | `app/ml/wc2026_model.py` (~fit + `joblib.dump`) | intl results | `wc2026_model.pkl` | N/A |
| Forecast A/B harness | `app/ml/ab_harness.py:250-288` | `forecast_scores` population | **in-memory only**; `"calibration": "none…"` (`:286`) | No artifact files |

### 2.3 Is there an NBA trainer?

**Partially.**

- The **generic** `FEATURE_COLUMNS` stack is NBA-oriented (Elo, rest, pace, ORtg,
  DRtg — `features.py:7-34`, `NBA_CONTEXT_COLUMNS:36-57`).
- Fixture sample under repo root `fixtures/` is tiny: **3** final scores, **5**
  odds rows, **3** games (local CSV counts).
- There is **no** separate production “NBA trainer” that packages artifacts into
  the prediction path. Canonical test market `nba-2025-01-15-lal-bos` is a
  product fixture, not a live trainer job.
- Prod scored population category histogram has **no `NBA` bucket** (see §3);
  “Sports” is the closest label.

### 2.4 Model registry vs predict path (critical gap)

- Registry: `app/ml/versioning.py` + admin
  `POST /api/v1/models/{id}/activate` (`api/v1/models.py:68-87`).
- Retrain cron: `cron(model_retrain_task, hour={4})` (`workers/tasks.py:1357-1358`),
  flag **`ML_RETRAIN_ENABLED=false` by default** (`config.py:598-599`).
- **No app service** calls `get_active_model` and injects
  `model_artifact_path` / `calibrator_path` / `feature_columns` into
  `predict_market`. Grep of `app/services` shows only the forecast_service
  comment that paths are absent.

**INFERRED:** activating a registry row today would **not** change
`PredictionLog.predicted_prob` until a wiring node exists.

---

## 3 Trainable data (per category, honest N)

### 3.1 Production counts (GET-only, 2026-07-25)

| Metric | Value | Source |
| --- | --- | --- |
| Scored LIVE forecasts | **206** | `GET /api/v1/track-record` → `n`; `GET /api/v1/eval/aggregates` → `market_count`; `GET /api/v1/system/model-ab` → `forecast_scored_count` / `resolved_count` |
| Mean Brier (scored locks) | ~0.0794 | same (locks are mostly market-implied passthrough historically) |
| Correlation clusters | **105** (threshold 100) | model-ab; `ab_ready=true` |
| Distinct families | 97 | model-ab population |
| A/B applied in prod | **false**; `verdict=no_winner` | model-ab |
| Opportunities open candidates | 103 | `GET /api/v1/opportunities` |
| With model predictions | **58** | same funnel `with_model_p` |
| After signal gate (default) | **0** | `empty_reason=no_validated_edge` |
| PAPER_TRADING_ONLY | true | health/detailed |
| External markets (autolock funnel) | external=905, open=684 | loops `forecast_autolock` detail |
| Catalog screener total | 1662 | `GET /api/v1/screener?limit=3` → `total` |

**Note on “204 graded”:** earlier internal notes (`STATE107-EVAL.md:13`) cited
204; live Railway read is **206**. Treat 204 as stale snapshot, not current.

**UNVERIFIED without admin key / SQL:** exact row counts for `odds_snapshots`,
`whale_events`, catalog `markets` resolved, `model_versions`. Public admin
stats (`/api/v1/admin/stats`) requires `X-Admin-API-Key` — not called.

**Whale loops (public):** `whale_flow` heartbeat `fetched=3 inserted=0`;
`whale_refresh` status `never`. Not a reliable training mass today.

### 3.2 Category histogram (scored LIVE population)

From prod `GET /api/v1/system/model-ab` → `population.category_histogram`:

| Category | N |
| --- | --- |
| Culture | 66 |
| Sports | 56 |
| Crypto | 46 |
| FIFA WC2026 | 23 |
| Tech | 8 |
| Economics | 5 |
| Politics | 2 |
| **Total** | **206** |

Venue: 100% polymarket on this population.

Family concentration warning: top families include repeated “bitcoin-above” (41)
and several Elon-tweet windows (15+15+12…) — independence is **less** than N.

### 3.3 Two training populations (do not conflate)

| Population | Loader | Identity keyspace | Label |
| --- | --- | --- | --- |
| **A. Forecast scores (A/B)** | `load_forecast_score_rows` (`forecast_ab_dataset.py:52-100`) | `ExternalMarket` + LIVE `ForecastLog` + `ForecastScore` | `actual_outcome` |
| **B. Catalog snapshots (retrain worker)** | `load_resolved_snapshot_feature_matrix` (`snapshot_dataset.py:11-81`) | `Market.slug` + `OddsSnapshot` | `winning_outcome` → `winner_yes` |

**INFERRED:** N(A)=206 verified. N(B) may differ and is **UNVERIFIED** here.

### 3.4 Features usable at prediction time AND reconstructible historically (no look-ahead)

Conservative table (provenance scout standard: assumption → **not usable**).

| Feature | Knowable at predict time today? | Reconstructible for historical training? | Verdict |
| --- | --- | --- | --- |
| Market implied YES | Yes — odds snapshot / lock column | Yes — `ForecastLog.market_implied_probability` or pre-close snapshots | **USABLE** |
| Time-to-lock / time-to-resolution hours | Yes if `lock_at`/`close_at` known | Yes — `ForecastLog.time_to_resolution_seconds` when set at lock (`forecast_service.py:201-228`) | **USABLE** (when non-null) |
| Binary outcome | No (future) | Yes — `ForecastScore.actual_outcome` / market resolution (**label only**) | **USABLE as label** |
| Category | Yes from catalog/external row | Yes on `ExternalMarket.category` (captured into alpha features when lock path runs — `alpha/provenance.py:108-115`) | **USABLE** if taken from row at lock, not re-labeled later |
| Platform | Yes | Yes | **USABLE** (low variance: all poly in scored set) |
| Volume at lock | Only if captured | Live lock path can capture (`provenance.py:101-107`); backfill explicitly **not reconstructible** (`:92-98`) | **USABLE only if snapshot stored**; else **NOT** |
| Price history / momentum | Only if captured at lock | Live path may pull last-hour odds (`provenance.py:136-142`); window not guaranteed for all rows | **USABLE only when AlphaFactorSnapshot has it** |
| Whale flow | Only if events exist pre-lock | Same | **Mostly NOT** given insert=0 heartbeats |
| News / debate sentiment | Only if captured | Same | **NOT** for bulk training without stored snapshot |
| NBA Elo / team ratings | Only with team identity + history | Catalog snapshot metadata must carry `nba_game` + pregame stats (`snapshot_dataset.py:84-174`); generic polymarket markets lack this | **NOT for generic markets** |
| Closing implied as **feature** | Would be look-ahead if used before close | Valid as **eval target** for CLV, not as train-time feature at lock | **NOT as feature**; **yes as CLV target** |
| Current live price re-read into past training rows | — | Look-ahead fabrication | **NOT** |

**A/B-sanctioned lock-time feature set (code law):**
`FORECAST_AB_FEATURE_COLUMNS = (market_implied_probability, time_to_resolution_hours)`
(`forecast_ab_dataset.py:26-29`). Anything richer needs proven lock-time storage.

### 3.5 What prediction_writer can compute **now** without new stores

Only what it already has: slug + latest implied (`prediction_writer.py:174-183` +
`forecast_service.py:97-101`). To serve an artifact it must **also** supply
numeric feature values matching `feature_columns` (e.g. implied + hours-to-lock
from `Market.lock_at`). That wiring does not exist yet.

---

## 4 Recommended first artifact + its honest limits

### 4.1 Recommendation

**Ship a calibrated binary classifier (logistic or small XGB) on lock-time
features:**

1. Primary features: `market_implied_probability`, `time_to_resolution_hours`
   (aligns with A/B harness + reconstructible locks).
2. Optional low-risk adds: one-hot / target-encoded **category** (only if encoded
   from lock-time category, not current taxonomy edits).
3. Train/eval on population **A** (`forecast_scores` LIVE resolved), walk-forward
   with embargo (`build_v40_folds` already exists).
4. Persist **joblib model + joblib calibrator** matching `_artifact_probability`.
5. Persist **`feature_columns` list** beside the artifact (trainer currently
   omits a sidecar — implementer must add one or embed in registry metrics).
6. Wire **`ForecastService.predict` / prediction_writer / autolock** to load
   active artifact paths + columns + fill feature values at predict time.
7. Keep `activate=False` default; human activate via admin models API.

**Do not** start with full NBA `FEATURE_COLUMNS` for generic Polymarket — those
columns default-fill when missing (`features.py:482-521`), which is silent
noise for non-NBA markets.

### 4.2 Honest limits on beating the closing line **today**

| Gate | Threshold | Available N | Status |
| --- | --- | --- | --- |
| Predictor significance sample | `DEFAULT_MIN_SAMPLE=100` (`backtesting/significance.py:30`) | 206 pooled | Pooled meets count; **per-category does not** (max Culture 66) |
| Alpha validator observations | `MIN_OBSERVATIONS=20`, `MIN_OOS_OBSERVATIONS=8` (`alpha/validator.py:30-31`) | depends on factor provenance + closing lines | Board still `no_validated_edge` |
| A/B cluster gate | 100 clusters | 105 | Ready for A/B math; `applied=false`, `verdict=no_winner` |
| Concentration | many multi-market families | 97 families | Effective independent N **≪** 206 **INFERRED** |

**Statement for implementers:**

- A model that is a mild calibration of market implied may reduce Brier vs a
  constant, but **claiming CLV-positive edge today is not supported** by
  deployed evidence: raw board edges are ~0 under passthrough; A/B reports
  **no winner**; opportunities default gate is empty for the right reason.
- Per-category N is **too small** to prove closing-line beat for Culture /
  Sports / Crypto alone under `min_sample=100`.
- **Correct first ship:** trainer + artifact package + predict-path wiring +
  scheduled retrain that **accrues** data, with CLV/`model_edge` validation
  remaining the **display authority**. Empty board while invalid remains
  honest.

### 4.3 What “success” looks like without lying

1. `PredictionLog.explanation.producer == "artifact"` (or FIFA where routed).
2. `model_p` systematically ≠ `market_p` when the model disagrees.
3. Walk-forward OOS Brier / CLV reported; board still empty until
   `AlphaRun` marks `model_edge` valid.
4. Registry version + digest stamped on locks/predictions (today always null —
   `forecast_service.py:132-137`).

---

## 5 Retrain / deploy path

### 5.1 Existing scheduled retrain (flag off)

```
ML_RETRAIN_ENABLED=false  (default)
ML_RETRAIN_MIN_ROWS=20
cron model_retrain_task @ 04:00 UTC  (workers/tasks.py:1357-1358)
```

Flow (`model_retrain.py:27-107`):

1. Load catalog resolved snapshot matrix.
2. Skip if rows < min.
3. `train_xgboost_from_feature_matrix` → files under `artifacts/retrain/<ts>/`.
4. `register_model_version(..., activate=False)`.
5. Log human recommendation to activate via
   `POST /api/v1/models/{id}/activate`.

**Gap:** activation updates DB pointer only; **predict path does not read it**.

### 5.2 FIFA precedent (works today)

| Step | Behavior |
| --- | --- |
| Data | Bundled `intl_results.csv` (~49k lines local) + fixture CSVs in package |
| Train | On first use if cache missing/stale (`predictor.py:108-148`) |
| Cache | Local `.model_cache.pkl` next to code (`:25`, `:152-162`) |
| Serve | In-process `FifaPredictor.calibrated_prob` — no registry |
| Deploy | Code + data files in image; cache may regenerate at boot (CPU cost) |

### 5.3 How a **generic** artifact should reach prod (options mapped to code)

| Mode | Precedent | Pros | Cons |
| --- | --- | --- | --- |
| **A. Bundled joblib in image** | admin/local ml_artifacts; FIFA pkl | Simple serve | Stale; dockerignore strips many joblibs; need allowlist path |
| **B. Train at boot / first request** | FIFA cache | Always fresh-ish | CPU/latency; need durable volume for cache on Railway |
| **C. Scheduled retrain worker + registry** | `model_retrain_task` | Matches D4 design | Must wire active model into predict; artifact path must exist on disk of the API process |
| **D. Object storage path in `ModelVersion.artifact_path`** | path is free-form string (`models.py:28`) | Multi-instance safe | **Not implemented** (no downloader found) |

**Practical recommendation for the fix node:** **C + explicit predict wiring**,
with artifact files written to a process-local dir that both retrain and API
share (or ship a known path in the Docker image for v1). Mirror FIFA’s
“load once, cache” for the active pair of joblibs after human activate.

### 5.4 Prediction writer deploy surface

- In-process loop: `main.py:627-673`, gated by
  `SCHEDULER_PREDICTION_WRITER_ENABLED` (default true, `config.py:193-195`).
- ARQ mirror: documented as `minute={5,35}` in prediction_writer module
  docstring / main comment.
- Prod loops response (2026-07-25) **did not list** a `prediction_writer`
  heartbeat name, yet `with_model_p=58` and desk `source=prediction_log`
  prove rows exist. **UNVERIFIED** whether current Railway process exposes
  that heartbeat or an older path wrote the rows; code path for writes is
  solely `prediction_writer.py` constructors in app code.

### 5.5 Evidence that prod is passthrough (not just empty)

`GET /api/v1/opportunities?signal_only=false` sample (2026-07-25): most rows
`model_p == market_p`, max edge observed in top set **0.004**. Desk sample
`pm-will-jesus-christ-return-before-2027`: `predicted_prob=0.0195` equals
`yes_price=0.0195`, confidence 0.5 (provisional).

---

## 6 Do-not-touch surface

| Surface | Why | Anchors |
| --- | --- | --- |
| Order path | LLM/agents cannot bypass risk | `RiskService` → `OrderIntent` → `OrderBookService`; OpenAPI description; `prediction_writer.py:28-29` never imports order path |
| `PAPER_TRADING_ONLY` | Must stay true | `config.py:13`, validator `:616-620`; health/detailed `paper_trading_only:true` |
| Alpha validator thresholds | Independent CLV authority for factors | `MIN_OBSERVATIONS`, bootstrap, OOS rules in `alpha/validator.py:28-35` — do not weaken to fill the board |
| Opportunities `signal_only` default / `model_edge` gate | Display law | `opportunities.py:27-34`, `:72-79`, `:83-101` — empty = honest when invalid |
| Predictor CLV significance defaults | Gate math | `DEFAULT_MIN_SAMPLE=100`, `DEFAULT_ALPHA=0.05` (`significance.py:30-32`) — do not lower to claim edge |
| Retrain auto-activate | Human only | `model_retrain.py:4-5`, `versioning.py:53-54`, E06 comments |
| Cash / payment / external execution language | Paper simulation product | AGENTS.md / OpenAPI |
| Fabricating historical `PredictionLog` backfill | Look-ahead | `prediction_writer.py:18-20` forbids |

**CLV gate remains display authority regardless of artifacts:** even a perfect
artifact only changes `model_p`. Validated opportunities still require
`AlphaRun` to mark `model_edge` valid (`opportunities.py:83-101`).

---

## Open decisions for the implementer / orchestrator

1. **Wire point:** inject active artifact into `ForecastService.predict` only,
   or also dual-path in prediction_writer / autolock / agents? (Single choke
   point at `ForecastService.predict` is lowest risk **INFERRED**.)
2. **Training population:** A (`forecast_scores` lock features) vs B (catalog
   odds snapshots)? A is what A/B and track-record already trust; B matches
   existing retrain worker but may not match lock features.
3. **Feature schema v1:** stick to A/B two features, or add category + volume
   only when `AlphaFactorSnapshot` proves availability rates?
4. **Sidecar for `feature_columns`:** registry metrics JSON vs adjacent
   `feature_columns.json` vs embed in joblib dict (FIFA/wc2026 style)?
5. **Artifact filesystem on Railway:** shared volume vs rebuild-in-image vs
   train-at-boot cache (FIFA-like)?
6. **Enable `ML_RETRAIN_ENABLED`?** Only after predict wiring exists; else
   retrain is write-only registry noise.
7. **FIFA vs generic:** keep FIFA slug router exclusive; do not force FIFA
   cache into `_artifact_probability`.
8. **Per-category models vs one pooled model?** Per-category N too small for
   CLV proof today; pooled first is the only defensible start.
9. **How to stamp `artifact_digest` / `model_version` on PredictionLog +
   ForecastLog** without inventing values when no artifact loaded?
10. **Prod loop visibility:** confirm prediction_writer heartbeat on Railway
    after deploy (currently absent from `/api/v1/system/loops` listing while
    PredictionLogs exist).
11. **odds_snapshots / whale_events training value:** run admin stats or SQL
    counts (GET/admin) before designing whale/momentum features — **UNVERIFIED
    N** in this scout.
12. **Accept that board may stay empty after artifact ship** until validator
    passes — product copy should say “model live, edge unproven” rather than
    force rows.

---

## Appendix: failure chain (one diagram)

```
OPEN markets (top 50 by volume)
  → prediction_writer (implied from odds_snapshots)
    → ForecastService.predict({slug, implied_yes, market_implied})
      → predict_market
        → _artifact_probability → None  (no paths/columns)
        → PRODUCER_IMPLIED_PASSTHROUGH
        → predicted_prob = implied
  → PredictionLog(model_p ≈ market_p)
  → opportunities ranks |model_p − market_p| ≈ 0
  → signal_only=true requires AlphaRun model_edge valid
  → after_signal_gate=0 → empty_reason=no_validated_edge
```

Fixing only the artifact files without wiring paths into the features dict
changes **nothing** on this chain.

---

*Scout complete. AutoLab: not applicable (mapping only, no iterative measure).*
