# NOWRITER-SWEEP — systematic reader/writer audit of every SQLAlchemy model

**Scope:** every `class X(Base)` in `backend/app/db/models.py` (71) and
`backend/app/models/social.py` (3) = **74 models**.
**Repo:** `E:/polymarket-worktrees/_integration` @ `9d447a3` (branch of `codex/alphaedge-base`).
**Mode:** read-only. Prod probes are GET-only against
`https://alphaedge-api-production-b9db.up.railway.app` (captured 2026-07-25 ~11:50–11:55 UTC).

## Method (so the result is reproducible, not another accident)

1. Enumerated model classes + `__tablename__` from the two model modules.
2. Scanned every `.py` under `backend/` (excluding `.venv`, `__pycache__`), bucketed
   each file as `prod` / `test` / `seed` / `script` / `migration`.
3. Classified each reference: **write** = constructor call, `insert()/update()/delete(Model)`,
   `session.add(Model(...))`; **read** = `select/query/get/join/selectinload(Model...)`.
   Alias imports (`Model as _Model`, and multi-line `Model as Alias,`) were resolved —
   the first pass missed `MarketSentimentSnapshot` and `Pod` for exactly this reason.
4. **Reachability pass:** for every production write, resolved the enclosing function and
   counted callers elsewhere in `app/`. A writer with zero callers is a dead writer even
   though grep says the table is "written".
5. Cron wiring pass: diffed `cron(...)` entries in `app/workers/tasks.py` against the
   in-process mirrors started in `app/main.py` (prod runs uvicorn only — no ARQ worker).
6. Prod corroboration on public GETs where one exists.

Verdict key: **HEALTHY** = reachable writer + reader · **NO-WRITER** = read but never
written by any reachable production path · **NO-READER** = written but never read ·
**DORMANT** = neither.

---

## Headline counts

| Verdict | Count | Models |
|---|---|---|
| HEALTHY | 62 | (table below) |
| **NO-WRITER** | **3** | `Evaluation`, `VenueMarketMatch`, `WalletPosition` |
| NO-READER | 1 | `PushSubscription` |
| DORMANT | 8 | `FeatureSnapshot`, `TrainingRun`, `DatasetSnapshot`, `PromptVersion`, `FailedJob`, `MarketSnapshot`(db), `FeatureVersion`, `EvalAggregate` |

Plus **8 AT-RISK cron-only writers** (section 3) — tables whose only automated writer is an
ARQ cron job that is *not* dual-wired into `app/main.py`, i.e. the known
"cron-dead-in-prod" gotcha. One of them (`WalletPositionSnapshot`) is empirically empty in
production, making it a de-facto fifth no-writer defect.

---

## 1. Verdict table

Readers/writers are `file:line` in `backend/`. "…+N" = additional call sites of the same kind.

### 1a. The defects

| Model (table) | Readers (sample) | Writers | Verdict | Prod evidence |
|---|---|---|---|---|
| `Evaluation` (`evaluations`) | `app/api/v1/eval_routes.py:18` (`GET /api/v1/eval/evaluations`), `app/api/v1/routes.py:195` (market snapshot), `app/eval/service.py:85` | `app/eval/service.py:43` in `EvalService.evaluate_market()` — reachable only from `app/workers/tasks.py:792 run_eval_on_resolve_task`, which is registered in `WorkerSettings.functions` (`tasks.py:1267`) but **never enqueued** (`grep enqueue_job app/` → 0 hits) and is not a `cron()` job | **NO-WRITER** | `GET /api/v1/eval/evaluations?limit=5` → `[]` (HTTP 200) |
| `VenueMarketMatch` (`venue_market_matches`) | `app/services/venue_gap_service.py:68` (gap refresh), `app/services/venue_match_service.py:70` `list_matches()` ← `app/api/v1/desk.py:89` | `app/services/venue_match_service.py:141` `_upsert_one()` ← `upsert_matches()` ← `match_and_persist()` ← `match_open_catalog()`. **All four have zero callers outside their own file** — `desk.py:89` calls only `list_matches()` (a read) | **NO-WRITER** | `GET /api/v1/venue-gaps` → `{"gaps":[],"count":0,"refreshed":null}`; `GET /api/v1/arb/opportunities` → `{"opportunities":[],"total":0}`; `GET /api/v1/desk?slug=…` → `"arb": null`; `/api/v1/system/loops` shows `venue_gap running=True detail="upserted=0 skipped_odds=0"` — the gap loop runs every 60s and finds **zero matches to price** |
| `WalletPosition` (`wallet_positions`) | `app/services/wallet_service.py:66` `smart_money_signal()` ← `app/api/v1/routes.py:288` (`GET /api/v1/signals/smart-money`) | `app/services/wallet_service.py:45` `WalletService.record_wallet_positions()` — **zero callers**; the only import of the module (`app/api/v1/routes.py:67`) calls `smart_money_signal()` only | **NO-WRITER** | `GET /api/v1/signals/smart-money?platform=polymarket&market_id=…` → `{"tracked_wallet_count":0,"positions":[]}` |
| `PushSubscription` (`push_subscriptions`) | **none in `app/`** (only `tests/test_notification_push.py:54`) | `app/services/notification_service.py:327` `store_push_subscription()` ← `app/api/v1/notifications.py:175` | **NO-READER** | no public GET; rows are accepted and stored but nothing ever reads them to deliver a web-push |

### 1b. Dormant (drop candidates)

| Model (table) | Readers | Writers | Verdict |
|---|---|---|---|
| `FeatureSnapshot` (`feature_snapshots`) | none | none | DORMANT — zero references anywhere in `backend/` incl. tests |
| `TrainingRun` (`training_runs`) | none | none | DORMANT — zero references |
| `DatasetSnapshot` (`dataset_snapshots`) | none | none | DORMANT — zero references |
| `PromptVersion` (`prompt_versions`) | none | none | DORMANT — zero references |
| `FailedJob` (`failed_jobs`) | none | none | DORMANT — zero references |
| `MarketSnapshot` (`market_snapshots`) | none | none | DORMANT — **name collision**: every `MarketSnapshot(...)` in `app/` is the dataclass at `app/forecasting/market_source.py:87`. The ORM class is never imported from `app.db.models` |
| `FeatureVersion` (`feature_versions`) | none | `app/ml/versioning.py:151` `register_feature_version()` — **zero callers** | DORMANT |
| `EvalAggregate` (`eval_aggregates`) | none | `app/eval/service.py:94` `EvalService.compute_aggregates()` — **zero callers** | DORMANT — `GET /api/v1/eval/aggregates` was already re-pointed at `forecast_scores` (`app/api/v1/eval_routes.py:33-45`, docstring: "Not the legacy evaluations table"); the table is now dead on both ends. Prod: `{"mean_brier":0.079…,"market_count":206}` — served from `_collect_calibration_data`, not this table |

### 1c. Healthy (62)

| Model (table) | Reader sample | Writer(s) | Notes / prod |
|---|---|---|---|
| `User` (`users`) | `api/v1/deps.py:41`, `api/v1/profile.py:112` …+25 | `api/v1/auth.py:41`; `api/v1/orders.py:242,500`; `services/settlement_service.py:68` | |
| `PaperOrder` (`paper_orders`) | `api/v1/portfolio.py:134`, `api/v1/calibration.py:115` …+20 | `api/v1/orders.py:256,509` | |
| `Follow` (`follows`) | `services/social_feed.py:48`, `services/social_follows.py:127` | `services/social_follows.py:65` | |
| `Watchlist` (`watchlists`) | `api/v1/watchlist.py:194`, `workers/daily_digest.py:120` …+7 | `api/v1/watchlist.py:157` | |
| `PortfolioEquitySnapshot` | `api/v1/portfolio.py:402`, `workers/daily_digest.py:65` | `services/analytics_equity.py:54` ← `workers/portfolio_equity.py` (wired `_portfolio_equity_loop`) | prod loop `portfolio_equity status=never` — daily job, uptime <5h |
| `NotifyPref` | `api/v1/notify_prefs.py:85` | `api/v1/notify_prefs.py:113` | |
| `Notification` | `services/notification_service.py:116` …+6 | `services/notification_service.py:89`; delete `workers/data_retention.py:268` | |
| `NotificationPreference` | `services/notification_service.py:47,67`, `notification_digest_service.py:40` | `services/notification_service.py:50,69` | |
| `MarketResolution` | `api/v1/market_detail.py:62`, `services/market_service.py:276` …+7 | `services/settlement_service.py:230` ← `settle_market` (4 callers incl. `workers/catalog_market_resolver.py`) | `catalog_market_resolve` loop running in prod |
| `Account` (`accounts`) | `services/ledger_service.py:15`, `api/v1/routes.py:544` …+9 | `services/paper_account_service.py:55`, `services/market_service.py:900`, `pods/runner.py:82`, `services/ledger_service.py:35` | |
| `Pod` (`pods`) | `api/v1/pods.py:21` | `pods/runner.py:85` `ensure_default_pods()` (alias `Pod as PodRow`) | `GET /api/v1/pods` → 3 pods with live equity curves |
| `PodTrade` | `api/v1/pods.py:34` | `pods/scoring.py:108` | `pod_runner` loop running, `scanned=300 scored=300` |
| `PodEquitySnapshot` | `api/v1/pods.py:26` | `pods/runner.py:185` | populated in prod |
| `Market` (`markets`) | 79 prod readers | `services/live_market_ingest.py:242`, `services/kalshi_live_ingest.py:304`, `services/market_service.py:79`, `api/v1/briefs.py:164` | `live_ingest` loop ok |
| `Order` (`orders`) | `services/order_book_service.py:57` …+9 | `services/order_book_service.py:295,353` | see AT-RISK #6 for expiry |
| `PaperSignal` | `services/paper_signal_service.py:86,95` | `services/paper_signal_service.py:64` ← `api/v1/routes.py:50` | |
| `Fill` (`fills`) | `api/v1/routes.py:165`, `services/order_history_service.py:137` | `services/order_book_service.py:453` | |
| `Position` (`positions`) | `api/v1/routes.py:674`, `services/heartbeat_manager.py:192` …+5 | `services/order_book_service.py:112`, `services/settlement_service.py:177` | |
| `LedgerEntry` (`ledger`) | `services/settlement_service.py:149` (idempotency guard only) | `services/ledger_service.py:54` | HEALTHY but **no user-visible reader** — no API surface exposes the ledger |
| `DomainEvent` | `api/v1/forecast_routes.py:242` (only `event_type LIKE 'mirror.%'`) | `events/bus.py:34` | HEALTHY-thin: non-`mirror.*` events are written and never read |
| `OddsSnapshot` | 53 prod readers | `data/snapshots.py:56`, `workers/price_feed_worker.py:74,270`; seeds `live_snapshot_seed.py:33`, `price_snapshot_seed.py:45` | `price_feed` + `live_tick` loops ok |
| `ModelVersion` | `api/v1/models.py:60` (`GET /api/v1/models`), `ml/versioning.py:84,102,110` | `ml/versioning.py:61` ← `workers/model_retrain.py:79` (**AT-RISK #2**); `ml/versioning.py:119` via `set_active_model` ← `api/v1/models.py:77` | `GET /api/v1/models` requires `X-Admin-API-Key` (422 without) |
| `ModelActivePointer` | `ml/versioning.py:137` `_get_or_create_pointer` ← `get_active_model`/`set_active_model` | `ml/versioning.py:139` | |
| `PredictionLog` (`prediction_logs`) | `api/v1/screener.py:40`, `api/v1/desk.py:68`, `api/v1/edge_history.py:60`, `api/v1/watchlist.py:92`, `api/v1/assistant.py:293`, `api/v1/routes.py:179`, `eval/service.py:32`, `pods/runner.py:105` …+2 | `services/prediction_writer.py:190` `write_model_predictions()` ← `prediction_writer_task` ← `_prediction_writer_loop` (`main.py:626`, boot-catch-up first) | **Previously-fixed defect, now verified live:** `GET /api/v1/screener?limit=50` → 23/50 rows carry `model_edge` |
| `Alert` (`alerts`) | `api/v1/activity.py:80` | `services/alert_dispatch.py:72` (6 importers incl. `workers/ops_alerts.py`) | |
| `SignalEvent` | `api/v1/feed.py:230`, `api/v1/alerts_feed.py:131`, `api/v1/desk.py:112`, `agents/analyst.py:123` …+17 | `services/signals_service.py:306`, `signals/alignment.py:217`, `signals/diff_engine.py:273`, `workers/tasks.py:514,646,710`, `api/v1/sports.py:206`; seed `services/signal_event_seed.py:103` | `GET /api/v1/desk` returns live `delta:price_jump` events |
| `WeatherForecastLog` | `workers/tasks.py:735,777` | `workers/tasks.py:746` ← `weather_scan_task` (wired) | HEALTHY but internal-only (no API reader); `weather_scan` loop ok, `GET /api/v1/weather/edges` → `cities:[]` |
| `TrackedWallet` | `services/wallet_service.py:67,99`, `workers/tasks.py:949` | `services/whale_tracker_service.py:44` ← `refresh_whales_task` (wired, weekly) | `whale_refresh status=never` (weekly cadence, uptime <5h) |
| `WalletPositionSnapshot` | `agents/tools.py:175,277` (whale concentration/activity → `/api/v1/smart-money`, `/api/v1/desk`), `services/whale_tracker_service.py:64` | `services/whale_tracker_service.py:94` ← `workers/tasks.py:959` `snapshot_whale_positions_task` | **AT-RISK #1** — cron-only, not in `main.py`. Prod: `top_holders.wallet_count=0` |
| `WhaleEvent` | `services/whale_flow_service.py:71,188` | `services/whale_flow_service.py:97` ← `whale_flow_task` (wired) | `whale_flow` loop ok, `detail=fetched=0 inserted=0` |
| `MarketSentimentSnapshot` | `alpha/provenance.py:557-565`, `signals/sentiment_trend.py:83-90` | `workers/tasks.py:378` in `run_news_scan()` (alias `_MarketSentimentSnapshot`) ← `news_scan_task` (wired) | `news_scan` loop ok |
| `VenueGap` (`venue_gaps`) | `api/v1/…` via `services/venue_gap_service.py:130,140`; `alpha/provenance.py:626` | `services/venue_gap_service.py:110` ← `refresh_gaps()` ← `venue_gap_task` (wired) | writer alive but **starved by `VenueMarketMatch`** — see defect #2 |
| `AnalystBrief` | `api/v1/briefs.py:97,121,195,207`, `api/v1/feed.py:242` …+10 | `agents/analyst.py:476`, `services/research_digest_service.py:185`, `signals/sentiment_debate.py:153` | `GET /api/v1/briefs?limit=1` → real LLM brief |
| `BriefClaim` | `api/v1/briefs.py:261`, `eval/claim_scorer.py:103`, `observability/drift.py:151` | `agents/analyst.py:499` | |
| `AnalystEvalAggregate` | `api/v1/briefs.py:224`, `api/v1/observability.py:139`, `observability/drift.py:141` | `eval/analyst_metrics.py:163` ← `analyst_aggregates_task` ← `_eval_loop` (`main.py:218`) | `eval` loop running |
| `AgentRun` | `services/agent_run_service.py:69,87,112` ← `admin/agent_routes.py` | `services/agent_run_service.py:43` | |
| `AgentRunStep` | `services/agent_run_service.py:103` | `services/agent_run_service.py:129` | |
| `ResearchSession` | `api/v1/terminal.py:73,107` | `api/v1/terminal.py:89`, `api/v1/skills.py:202` | |
| `ResearchStep` | `api/v1/terminal.py:52,202` | `services/terminal_research_service.py:327,362` | |
| `Skill` (`skills`) | `api/v1/skills.py:67,78,125…` +12 | `api/v1/skills.py:170,266`, `api/v1/terminal.py:215`; seed `services/skill_seed_service.py:63` (wired at `main.py:847`) | |
| `SkillRating` | `services/marketplace_rating_service.py:17` | `…:20` ← `api/v1/skills.py:28` | |
| `Scanner` | `api/v1/scanners.py:150,223,239…` +15 | `api/v1/scanners.py:197,583`; seed `services/scanner_seed_service.py:238` (wired at `main.py:849`) | |
| `ScannerRating` | `services/marketplace_rating_service.py:39` | `…:44` | |
| `ScannerVersion` | `services/scanner_version_service.py:19,61` | `…:26` ← `api/v1/scanners.py:41` | |
| `ScannerRun` | `api/v1/scanners.py:140,263,327…` +6 | `services/scanner_executor_service.py:612` | |
| `Subscription` | `api/v1/subscriptions.py:53,79,102`, `services/notification_producers.py:425` | `api/v1/subscriptions.py:61` (note: `core/event_bus.py:84 Subscription(...)` is an unrelated in-memory class) | |
| `JobRun` (`job_runs`) | `admin/routes.py:177,195`, `api/v1/admin_markets.py:241`, `ml/ab_harness.py:99` | 29 write sites across `workers/*` and `admin/routes.py` | |
| `Forecaster` | `api/v1/calibration.py:51`, `services/forecaster_service.py:43,59` | `services/forecaster_service.py:30`, `workers/forecast_autolock.py:58` | `forecast_autolock` loop ok |
| `ExternalMarket` | `api/v1/calibration.py:67`, `api/v1/backtest.py:316` …+16 | `services/external_market_service.py:73`, `workers/external_market_bridge.py:202` | `external_market_bridge candidates=25 bridged=0` |
| `ForecastLog` | `api/v1/market_locked_forecast.py:128`, `services/forecast_dashboard_service.py:204` …+14 | `services/forecast_service.py:206` | |
| `AgentClone` | `agents/clone_service.py:116,131,148,230`, `services/clone_leaderboard_service.py:321,370` | `agents/clone_service.py:92,179,183,215` ← `api/v1/clones.py:41` | `GET /api/v1/clones/leaderboard` → `count:0` (user-created; no users have cloned) |
| `AgentCloneRun` | `agents/clone_service.py:335`, `services/clone_leaderboard_service.py:170` | `agents/clone_service.py:288` | |
| `ForecastScore` | `api/v1/calibration.py:53,66`, `api/v1/track_record.py:77`, `eval/forecast_drift.py:122` …+8 | `services/scoring_service.py:93` | `GET /api/v1/calibration/latest` → `markets_evaluated: 206` |
| `AlphaFactorSnapshot` | `alpha/alpha_service.py:81`, `alpha/provenance.py:55,180` | `alpha/provenance.py:163` ← `alpha_model_task` | `GET /api/v1/alpha/runs` → `factor_snapshots: 202` |
| `AlphaClosingLine` | `alpha/provenance.py:221,270` | `alpha/provenance.py:251` | **Previously-fixed defect, verified live:** `closing_lines: 154`, `closing_line_gaps: 48` |
| `AlphaRun` | `alpha/alpha_run_service.py:32,137,173,179,191`, `api/v1/opportunities.py:90` | `alpha/alpha_run_service.py:88` | run_date `2026-07-25` present |
| `BacktestRun` | `api/v1/backtest.py:235,253` | `api/v1/backtest.py:193` (on-demand POST); `workers/tasks.py:1152` `nightly_backtest_task` (**AT-RISK #3**) | `GET /api/v1/backtest/runs` → `[]` |
| `AgentMemory` | `api/v1/memories.py:63`, `services/memory_service.py:270` | `services/memory_service.py:230` ← `services/scoring_service.py:18`, `api/v1/admin_markets.py:29` | `GET /api/v1/memories` → populated |
| `ForecastDriftSnapshot` | `eval/forecast_drift.py:205` ← `api/v1/eval_routes.py` | `eval/forecast_drift.py:170` ← `drift_detect_task` (wired) | `GET /api/v1/eval/drift` → 3 hourly rows |
| `HeartbeatDecisionLog` | `api/v1/heartbeat.py:118` | `services/heartbeat_manager.py:370,421` (wired `_heartbeat_manager_loop`) | `GET /api/v1/heartbeat/decisions` → populated; loop `logged=10` |
| `StoryComment` | `services/social_service.py:170,328` | `services/social_service.py:362` | |
| `StoryReaction` | `services/social_service.py:132,152,395,418` | `services/social_service.py:427` | |
| `WatchlistShare` | `services/social_service.py:462,496` | `services/social_service.py:500` | |

---

## 2. Ranked fix list — which NO-WRITER gaps starve user-visible surfaces

| # | Gap | Starved surfaces | Size | Fix shape |
|---|---|---|---|---|
| 1 | **`venue_market_matches` NO-WRITER** — `VenueMatchService.match_open_catalog()/match_and_persist()/upsert_matches()` have no production caller | `GET /api/v1/venue-gaps` (empty), `GET /api/v1/arb/opportunities` (empty), `GET /api/v1/desk` → `arb: null`, cross-venue block of the desk UI, `alpha/provenance.py:626` gap provenance | **S–M** | Call `VenueMatchService(session).match_open_catalog(...)` at the head of `venue_gap_task` (`workers/tasks.py:854`) before `VenueGapService.refresh_gaps()`. The matcher is already written, tested and confidence-gated — it is simply never invoked. Bound it (`venue_gap_match_limit` already exists) so the 60s loop stays cheap. |
| 2 | **`wallet_positions` NO-WRITER** — `WalletService.record_wallet_positions()` has no caller | `GET /api/v1/signals/smart-money` → `{"tracked_wallet_count":0,"positions":[]}` (permanently) | **M** | Either wire `record_wallet_positions` into `snapshot_whale_positions_task` (it already fetches the same Polymarket data-api positions that `whale_tracker_service.snapshot_and_diff` consumes), or retire `/api/v1/signals/smart-money` in favour of `/api/v1/smart-money`, which reads `wallet_position_snapshots`. Two overlapping whale-position stores is the root cause. |
| 3 | **`wallet_position_snapshots` cron-only writer** (AT-RISK #1, empirically empty) | `GET /api/v1/smart-money` → `top_holders.wallet_count: 0`, `recent_large_flows.whale_count: 0`; embedded verbatim in `GET /api/v1/desk`; `agents/tools.py` whale tools used by the analyst | **S** | Add `_whale_position_snapshot_loop()` in `app/main.py` mirroring `cron(snapshot_whale_positions_task, minute=*/3)`, flag-gated like its 20 siblings. This is the same class of bug the four earlier defects were. |
| 4 | **`evaluations` NO-WRITER** (legacy) | `GET /api/v1/eval/evaluations` → `[]`; the `evaluation` block of `GET /api/v1/markets/{slug}/snapshot` (`api/v1/routes.py:195`) is always null | **S** | Decide and commit: either enqueue `run_eval_on_resolve_task` from `settle_market`, or delete the route + `EvalService.evaluate_market` + the table (the calibration family at `/eval/aggregates` + `/calibration/latest` + `/track-record` already supersedes it and is healthy at 206 markets). Deletion is the honest option. |
| 5 | **`push_subscriptions` NO-READER** | Users can grant push permission and the subscription is stored, but **no code ever delivers a push** — a silent promise in the notifications UI | **M** | Either add a dispatcher that reads `push_subscriptions` in `notification_service` fan-out, or remove the `POST /api/v1/notifications/push` surface so the UI stops claiming a capability. |
| 6 | **`backtest_runs` automated writer dead** (AT-RISK #3) | `GET /api/v1/backtest/runs` → `[]` unless a user manually POSTs | **S** | Wire `nightly_backtest_task` in-process (still behind `BACKTEST_NIGHTLY_ENABLED`). |
| 7 | **8 DORMANT tables** | none (dead weight, schema noise, misleading to future agents) | **S** | Drop `feature_snapshots`, `training_runs`, `dataset_snapshots`, `prompt_versions`, `failed_jobs`, `market_snapshots`, `feature_versions`, `eval_aggregates` + their model classes. Note `MarketSnapshot` must be deleted carefully — the *dataclass* of the same name in `app/forecasting/market_source.py` is load-bearing. |

---

## 3. AT-RISK: cron-only writers not dual-wired in `app/main.py`

Prod runs uvicorn only (no ARQ worker), so an ARQ `cron()` job with no in-process mirror in
`app/main.py` never executes. Diff of `cron(...)` in `backend/app/workers/tasks.py:1302-1365`
against the loops started in `backend/app/main.py:854-919`:

| # | Cron task (`tasks.py`) | Tables it writes | In-process mirror? | Assessment |
|---|---|---|---|---|
| 1 | `snapshot_whale_positions_task` (`tasks.py:932`, `minute=*/3`) | `wallet_position_snapshots`, `whale_events` | **No** | **Effectively a 5th no-writer.** Prod `/api/v1/smart-money` → `wallet_count 0`, `whale_count 0`. Highest-value fix in this section. |
| 2 | `model_retrain_task` (`workers/model_retrain.py`, daily 04:00) | `model_versions`, `job_runs` | **No** | Also flag-gated `ML_RETRAIN_ENABLED=false`. `ModelVersion` still has an admin API writer (`api/v1/models.py:77`), so not fatal — but no model is ever retrained in prod. |
| 3 | `nightly_backtest_task` (`tasks.py:1098`, daily 02:00) | `backtest_runs`, `job_runs` | **No** | Corroborated: `GET /api/v1/backtest/runs` → `[]`. |
| 4 | `capture_market_snapshots_task` (`tasks.py:42`, hourly) | `job_runs` (+ `pipeline/ingest.py` capture side effects) | **No** | `/admin/market-snapshot-captures` (JobRun-backed) will always be empty. Admin-key gated, not spot-checkable read-only. INFERRED. |
| 5 | `capture_historical_closing_snapshots_task` (`tasks.py:68`) | `job_runs` | **No** (admin POST route only, `admin/routes.py:103`) | Manual-only. |
| 6 | `order_expiry_task` (`workers/order_expiry.py`, every minute) | `orders` (status update), `job_runs` | **No** | Open limit orders past expiry are never expired in prod. INFERRED — no public GET exposes order TTL. |
| 7 | `ingest_odds_task` (`tasks.py:114`, daily 12:00) | `odds_snapshots` (from `fixtures/`) | **No** | Low risk — `price_feed_worker` + `live_tick` are wired and are the real prod writers. Fixture ingest in prod would arguably be wrong anyway. |
| 8 | `nightly_profile_refresh_task` (`tasks.py:1192`, daily 03:30) / `fetch_news_signals_task` (`tasks.py:220`, hourly) | no ORM table (cache/profile artifacts) | **No** | Cache warm only; `news_scan_task` (wired) covers the DB-writing path. |

### 3b. Secondary finding — the loop observability allowlist is stale

`app/api/v1/system.py:42` defines `_ALL_LOOPS` as a hardcoded tuple, and
`GET /api/v1/system/loops` iterates *that* rather than `LOOP_INTERVALS`
(`app/observability/loop_state.py:29`). Six loops that do record heartbeats are therefore
invisible on the status endpoint: `prediction_writer`, `scanner_scheduler`,
`news_mispricing`, `unusual_flow`, `alpha_model`, `notification_digest`.

Confirmed against prod: `/api/v1/system/loops` returns 26 rows and omits `prediction_writer`
even though `LOOP_INTERVALS` contains `"prediction_writer": 1800`. This is the exact blind
spot that let the earlier "reader with no writer" bugs stay hidden — the dashboard built to
answer "is anything actually running?" cannot see the loop that feeds twelve
`PredictionLog` consumers. **Fix (S): derive `_ALL_LOOPS` from `LOOP_INTERVALS` keys.**

---

## 4. Notes on evidence quality

- Everything in the tables is grep-verified `file:line` or a captured prod response.
- Items labelled **INFERRED** (AT-RISK #4, #6) have code evidence but no read-only prod probe,
  because the corroborating surfaces are admin-key gated.
- `GET /api/v1/models` and `/admin/*` returned 422 (missing `X-Admin-API-Key`); no credential
  was supplied or sought.
- The three previously-found defects that have since been fixed (`alpha_closing_lines`,
  the calibration path, `prediction_logs`) all come back **HEALTHY** under this method and are
  confirmed populated in prod — which is the control that says the sweep discriminates.
