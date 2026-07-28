# SCHED-DIAG117 — Scanner scheduler, background loops, model-label honesty

**Role:** Diagnostician (read-only)  
**Repo:** `E:/polymarket-worktrees/_integration`  
**Date:** 2026-07-27  
**Targets:** prod API `https://alphaedge-api-production-b9db.up.railway.app`, Railway project `alphaedge-api` / env `production` / service `alphaedge-api`  
**Sources:** `SHIP-E2E-TEST.md` defects D6 / D7 / D0; live public GETs; code paths; Railway variable **names only** (no values); Railway logs (no secrets).  
**Scope:** diagnosis only — no source edits, secrets, push, or deploy.

**AutoLab:** not applicable (no iterative measure)

---

## Executive verdict

| ID | Ship claim | Diagnostic verdict |
|---|---|---|
| **D6** | 10 ACTIVE scanners, scheduler beating, zero runs ever | **Partially incorrect.** Scheduler **does** run scanners. List/featured APIs omit `latest_run`, so UI shows `last run never`. Heartbeat `due=0 ran=0` is **interval gate** after real runs, not a dead dispatcher. |
| **D7** | polymarket_ws ok-but-stale; live_ingest overdue; kalshi_ws + retention never | **Mixed:** kalshi_ws = **flag-off**; retention / equity / digest = **honest-idle sleep-first** under ~4.4h uptime; live_ingest = **demand-paced idle** (can exceed advertised 1800s); polymarket_ws = **broken heartbeat contract** (status stuck `ok`, detail stuck `stream loop starting`). |
| **D0** | `/eval` headlines Brier as model skill while producer is market echo | **Correct.** Provenance is `implied_passthrough`. Copy claims "model" in multiple surfaces; numbers must not change — labels must. |

**Process uptime at re-probe:** ~15 934 s (~4.4 h).  
**Plan from `/api/v1/system/loops`:** `["price_feed","live_ingest","live_tick","polymarket_ws"]` (WS plan only — not the full set of in-process loops).

---

## D6 — Active scanners, zero runs (UI lie; scheduler alive)

### CAUSE (primary)

**List surfaces never attach `latest_run`.**  
`GET /api/v1/scanners/` and `GET /api/v1/scanners/featured` call `_scanner_out(s)` with no run load. Default `latest_run=None` always. FE `ScannerCard` then renders **last run · never**.

Detail + runs endpoints **do** load runs. Prod has many real runs.

Secondary (not the ship defect, but real product state): many scheduled runs finish `status: "empty"` with `counts.aligned: 0` — the schedule fires, the pipeline finds no aligned candidates. That is not "never ran."

### Evidence (step-by-step)

1. **Ship symptom** — `SHIP-E2E-TEST.md` D6: 10 cards `ACTIVE` / `last run never` / `· 0`; featured `latest_run: null`; loop `scanner_scheduler` `ok`.

2. **Loop heartbeat (re-probe)** — `scanner_scheduler`: `running=true`, `status=ok`, `detail=active=10 due=0 ran=0`, interval 300 s.  
   - `active=10` ⇒ query `Scanner.status == "active"` works; **owner-null seeds are included**.  
   - `due=0` / `ran=0` is a **single tick summary**, not lifetime history.

3. **Flag path** — `main.py` starts `_scanner_scheduler_loop` when `settings.scheduler_scanners_enabled` (env **`SCHEDULER_SCANNERS_ENABLED`**, default **True**). Railway: key **not present** ⇒ default on.  
   Task gate: `scanner_scheduler_task` returns `skipped: disabled` only if flag false; detail would be `skipped:disabled` — not observed.

4. **Dispatch path**  
   - `main._scanner_scheduler_loop` → `workers.tasks.scanner_scheduler_task` → `scanner_scheduler_service.run_due_scanners` → `run_scanner`.  
   - Due logic (`is_scanner_due`): status must be `"active"`; if `last_started_at` set, wait `interval_minutes`; if last **fired** (`counts.aligned >= 1`), wait `cooldown_minutes`.  
   - Never-run scanners are due immediately (unit test `test_pick_due_scanners_interval_cooldown_paused`).  
   - `market_hours_only` false on all 10 seed specs ⇒ calendar gate open.

5. **API list bug** — `backend/app/api/v1/scanners.py`:  
   - `list_scanners` ≈ L342: `return [_scanner_out(s) for s in scanners]` — **no** `_latest_run`.  
   - `featured_scanners` ≈ L439: same.  
   - `get_scanner` ≈ L459–462: **does** load latest run.  
   - `list_scanner_runs` ≈ L646–660: returns runs.

6. **Prod proof runs exist** (public GET, seed scanner `76cf80b9-…` Cross-Venue Divergence):  
   - `latest_run.started_at = 2026-07-27T17:40:55Z`, `status=empty`, `is_test=false`, counts `universe=20 candidates=0 aligned=0`.  
   - `GET …/runs` returned 20 rows on a ~hourly cadence.  
   - Other seeds also have latest runs (e.g. NBA Sharp Money completed with `aligned=1`; Model Edge Radar completed with `aligned=0`).

7. **Usage / trending** — `/api/v1/usage/summary` totals **scanner_runs=319** (14d); days 2026-07-25..27: 105 / 123 / 91.  
   - `/scanners/trending`: run_count 63…3 but **`latest_run` still null** (same list omission).

8. **FE** — `ScannersShell` uses `listScanners` only; `ScannerCard.tsx` L116–132: missing `latest_run` → literal **never**. StarRating with no ratings explains ship’s **`· 0`** (ratings, not run count).

9. **Why heartbeat said `due=0`** — After a run at T, interval (e.g. 60 min) blocks until next window. At sample times with all 10 inside interval, pure picker returns empty → `due=0 ran=0` while scheduler is healthy. **Not** load-guard: guard returns `active=0` + `skipped_load_guard` (not seen).

### Ruled out

| Hypothesis | Status |
|---|---|
| `SCHEDULER_SCANNERS_ENABLED` off | Ruled out (loop running, active=10, runs in DB) |
| Owner-null seeds excluded | Ruled out (`owner: null` seeds have runs) |
| Wrong status query | Ruled out (`status == "active"` matches seeds) |
| Interval/cooldown permanently blocks never-run | Ruled out for never-run; **does** gate after real starts |
| Executor never called | Ruled out (ScannerRun rows, non-test) |

### One-line fix

**In `list_scanners` / `featured_scanners` / trending base rows, batch-load latest `ScannerRun` per id and pass into `_scanner_out(..., latest_run=…)`** (same as `get_scanner`). Optional FE: after list, do not treat null latest_run as lifetime never without a detail fetch.

---

## D7 — Loops: flag-off vs broken vs honest-idle

### Railway variable **names** (presence only; no values)

| Name | Present on prod service? | Role |
|---|---|---|
| `KALSHI_WS_ENABLED` | **yes** | gates `kalshi_ws` in `background_loop_plan` |
| `POLYMARKET_WS_ENABLED` | no | default True in `config.py` |
| `LIVE_FEED_ENABLED` | no | default True; required for WS + live_ingest/tick |
| `LIVE_INGEST_INTERVAL_SEC` | no | default 1800 |
| `SCHEDULER_IDLE_INTERVAL_SEC` | no | default 3600 (idle pace ceiling) |
| `SCHEDULER_SCANNERS_ENABLED` | no | default True |
| `SCHEDULER_JOBRUN_RETENTION_ENABLED` | no | default True |
| `JOBRUN_RETENTION_ENABLED` | no | default True (task-level) |
| `SCHEDULER_DATA_RETENTION_ENABLED` | no | default True |
| `DATA_RETENTION_ENABLED` | no | default True |
| `SCHEDULER_PORTFOLIO_EQUITY_ENABLED` | no | default True |
| `SCHEDULER_DAILY_DIGEST_ENABLED` | no | default True |
| `ML_RETRAIN_ENABLED` | no | loop detail shows skipped false |
| `BACKTEST_NIGHTLY_ENABLED` | no | loop detail shows skipped false |
| `PODS_ENABLED` | yes | pod_runner running |
| `HEARTBEAT_MANAGER_ENABLED` | yes | heartbeat_manager running |
| `PAPER_TRADING_ONLY` | yes | required paper SIM |

Related defaults: `config.py` `kalshi_ws_enabled` / `polymarket_ws_enabled` default **True**; plan omits `kalshi_ws` ⇒ effective **False** via set `KALSHI_WS_ENABLED`.

### Classification table

| Loop | Ship note | Class | Exact env / code | Evidence |
|---|---|---|---|---|
| **kalshi_ws** | never | **FLAG-OFF** | **`KALSHI_WS_ENABLED`** | `planned:false`, `status:never`; plan has no `kalshi_ws`; Railway has the key; defaults alone would include it |
| **polymarket_ws** | ok + ~4h-stale heartbeat | **BROKEN heartbeat / misleading status** | **`POLYMARKET_WS_ENABLED`** (default on; not set on Railway) | `planned:true`, detail forever `"stream loop starting"`, age ≈ uptime; heartbeat only at outer try start (`main._polymarket_stream_loop`); inner reconnects do not re-heartbeat. Logs: `[polymarket.ws] stream session ended` / `reconnecting` — stream is not silent-dead, but **status cannot go stale** |
| **live_ingest** | 1.9× overdue, still ok | **HONEST-IDLE demand pace** (not hard fail) | **`LIVE_INGEST_INTERVAL_SEC`** (1800) + **`SCHEDULER_IDLE_INTERVAL_SEC`** (3600) | After work, `_paced_sleep(1800, idle)`; idle can sleep up to **3600 s** while still `ok`. Ship 1.9× of 1800 is inside that ceiling. Re-probe age ~1267 s (healthy). Advertised `interval_sec:1800` understates idle cadence |
| **jobrun_retention** | never | **HONEST-IDLE sleep-first** (at current uptime) | **`SCHEDULER_JOBRUN_RETENTION_ENABLED`** + task **`JOBRUN_RETENTION_ENABLED`** | Loop: sleep **86400** first, then task, then heartbeat. Uptime ~4.4 h << 24 h ⇒ `never` expected. Flags default on; Railway keys absent |
| **data_retention** | never | **HONEST-IDLE sleep-first** | **`SCHEDULER_DATA_RETENTION_ENABLED`** + **`DATA_RETENTION_ENABLED`** | Same 86400 sleep-first pattern |
| **portfolio_equity** | never (ship) | **HONEST-IDLE sleep-first** | **`SCHEDULER_PORTFOLIO_EQUITY_ENABLED`** | Sleep **21600** (6 h) first; uptime 4.4 h ⇒ still never |
| **daily_digest** | never (ship) | **HONEST-IDLE sleep-first** | **`SCHEDULER_DAILY_DIGEST_ENABLED`** | Same 21600 sleep-first |
| **plan vs running** | 29/34 planned false | **By design (narrow plan)** | `background_loop_plan` only lists price_feed + live_* + WS | In-process schedulers use separate `SCHEDULER_*` flags; `planned` is **not** “should this loop exist” for scanners/retention/etc. |

### Code anchors

- Plan: `backend/app/data/streams/runner.py` `background_loop_plan`  
- Loop start gates: `backend/app/main.py` lifespan (~1218–1281)  
- WS outer heartbeat only: `main._polymarket_stream_loop` / `_kalshi_stream_loop`  
- Retention/equity sleep-first: `main._jobrun_retention_loop`, `_data_retention_loop`, `_portfolio_equity_loop`, `_daily_digest_loop`  
- Intervals registry: `backend/app/observability/loop_state.py` `LOOP_INTERVALS`  
- Loops API: `backend/app/api/v1/system.py` `get_loops` (`planned = name in plan` only)

### One-line fixes / env names

| Item | Fix |
|---|---|
| kalshi_ws | Set **`KALSHI_WS_ENABLED=true`** only if Kalshi WS is intended (name only; ops decision). |
| polymarket_ws | Re-heartbeat on reconnect / periodic stream tick; treat age ≫ 0 for continuous loops as **stale**, not `ok`. |
| live_ingest | Document or expose effective idle interval (`max(LIVE_INGEST_INTERVAL_SEC, SCHEDULER_IDLE_INTERVAL_SEC)`), or mark overdue only past idle ceiling. |
| retention / equity / digest | Boot catch-up once (like `whale_refresh`), or accept `never` until first long sleep elapses. |

---

## D0 — “Model” labels over `implied_passthrough` Brier

### CAUSE

Scored forecast population is market-implied passthrough, not a trained artifact win.

- Prod `GET /api/v1/system/model-ab` → `population.provenance.provenance_model_types: ["implied_passthrough"]` (193/193 provenanced).  
- Predictor default producer: `PRODUCER_IMPLIED_PASSTHROUGH` when no artifact (`backend/app/forecasting/predictor.py` L26–33, L80–86).  
- UI still frames aggregate Brier / accuracy as **model** skill.  
- **Do not change the numbers** — only the words until a non-passthrough artifact is active.

### Ship / re-probe numbers (unchanged)

- Brier **0.08114884475555556** on `calibration/latest`, `eval/aggregates`, `track-record`.  
- Resolved summary accuracy **0.8711**, mean Brier **0.081149**, n **225**.  
- Screener: most non-null edges ≈ 0 (market echo).

### Label map for copy-fix (file:line → string)

Primary ship surfaces (headline “model performance”):

| file:line | String / claim |
|---|---|
| `frontend/src/app/eval/page.tsx:92` | kicker **`Model proof`** |
| `frontend/src/app/eval/page.tsx:100` | **`Mean Brier (7d)`** (unqualified; implies model metric) |
| `frontend/src/app/eval/page.tsx:115` | **`Ensemble vs single-model`** |
| `frontend/src/app/eval/page.tsx:160` | **`Single-model Brier`** |
| `frontend/src/app/resolved/page.tsx:70` | **`model {row.modelLabel}`** on cards |
| `frontend/src/app/resolved/page.tsx:132` | subtitle **model's probability at close** |
| `frontend/src/app/resolved/page.tsx:149` | **`Model accuracy`** |
| `frontend/src/app/resolved/page.tsx:160` | **`Mean Brier`** (same framing as model accuracy row) |

Other user-visible “model” claims that read as skill while producer is passthrough:

| file:line | String / claim |
|---|---|
| `frontend/src/app/compare/page.tsx:76` | **`Model vs market`** |
| `frontend/src/app/compare/page.tsx:80` | **`model {col.modelLabel}`** |
| `frontend/src/app/s/[slug]/share-client.tsx:100` | **`Model vs market`** |
| `frontend/src/app/s/[slug]/share-client.tsx:103` | **`model {view.modelLabel}`** |
| `frontend/src/app/categories/[category]/category-client.tsx:68` | **how far the model sits from the market** / **how the model has actually done** |
| `frontend/src/app/alerts/page.tsx:99` | **`Model mispricings`** |
| `frontend/src/app/alerts/page.tsx:147` | **model mispricings** |
| `frontend/src/app/opportunities/page.tsx:97` | **stored model probability** / **model-vs-market scanner** |
| `frontend/src/app/opportunities/layout.tsx:7` | meta **Model-vs-market opportunity board** |
| `frontend/src/app/signals/layout.tsx:7` | meta **Model-vs-market signal desk** |
| `frontend/src/app/screener/layout.tsx:12` | meta **ranked by model edge** |
| `frontend/src/app/screener/page.tsx:5` | comment/user framing **ranked by model edge** |
| `frontend/src/app/home/page.tsx:170` | **`Model A/B readiness`** |
| `frontend/src/app/home/page.tsx:284` | **`Model A/B readiness`** |
| `frontend/src/components/BacktestWalkForward.tsx:131` | **`Model Brier`** |
| `frontend/src/components/SelfServeBacktest.tsx:135` | **`Model Brier`** |
| `frontend/src/components/BriefEvidencePanel.tsx:30` | **`Model vs market`** |
| `frontend/src/components/DeskIntelligencePanel.tsx:112` | **`Model vs market`** |
| `frontend/src/components/DeskIntelligencePanel.tsx:116` | **`model {view.edge.modelLabel}`** |
| `frontend/src/components/ForecastDriversPanel.tsx:48,57,70` | **`Why the model thinks this`** |
| `frontend/src/components/ForecastDriversPanel.tsx:78` | **`model {…} vs market {…}`** |
| `frontend/src/components/EdgeHistoryChart.tsx:50,52,109,118,135` | **`Model vs market`** history labels |
| `frontend/src/components/EdgeHistoryChart.tsx:159` | **`model {view.latest?.modelLabel}`** |
| `frontend/src/components/SignalEvidence.tsx:14` | **`model {(evidence.modelP * 100)…}%`** |
| `frontend/src/components/DecisionCard.tsx:418` | **`Provisional — model not yet CLV-validated`** |
| `frontend/src/lib/backtest-summary-api.ts:121` | verdict **`model beats market`** |

Suggested relabel pattern (for a copy-fix node; not applied here):  
**“Market baseline (implied passthrough)”** / **“Market Brier”** / **“Market accuracy”** until `provenance_model_types` includes a non-passthrough producer (artifact / trained model).

### One-line fix

**Relabel eval/resolved headlines from “Model …” to “Market baseline …” (or “Implied passthrough …”) while `provenance_model_types == ["implied_passthrough"]`; leave numeric fields untouched.**

---

## Cross-links (ship defects → this report)

| Ship | Section |
|---|---|
| D6 | § D6 |
| D7 | § D7 |
| D0 | § D0 |

---

## Stop

Diagnosis complete. No code changes, no deploys, no secret values recorded.
)
