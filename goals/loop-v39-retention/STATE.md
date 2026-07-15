# loop-v39-retention — STATE

## LOOP LOG

| ticket | date | result | proof |
|--------|------|--------|-------|
| R1 | 2026-07-15 | DONE (audit only, no code) | commit below; cited consumer table |

---

## SHARED FILE CLAIMS

| file | ticket | status |
|------|--------|--------|
| (none yet — R1 is STATE.md only) | R1 | released |

---

## R1 — Consumer audit (binding for R2)

Audit date: 2026-07-15. Branch `loop39/retention` @ `f039b77` + this commit.
Scope: **readers** of `odds_snapshots`, `signal_events`, `notifications` (app code; writers listed only for context). History depth = what each consumer actually needs so retention cannot break it.

### HARD constraints derived from consumers (R2 must honor)

1. **Never delete** `odds_snapshots` rows referenced by `prediction_logs.odds_snapshot_id` (FK, `models.py:533-535`) — CLV/closing-line eval fallback (`eval/service.py:76-81`).
2. **Never delete full-resolution ticks inside active scoring / CLV lookback windows** — claim/clone scoring needs every tick between claim time and horizon (`claim_scorer.py:78-94`, `clone_leaderboard_service.py:133-151`); horizons are minutes–hours (default 60m), so the full-res retention floor must cover the max practical horizon with margin.
3. **Beyond full-res window**: **downsample only** — keep **daily closes** (last tick per `market_slug` + `source` per UTC day). Long-horizon consumers (ML dataset, backtest replay, edge-history as-of joins) tolerate daily resolution if recent high-freq ticks remain.
4. **signal_events**: hard prune OK beyond **30d** default (matches digest max window `alerts_feed.py:42`); feeds are limit/order-desc, not full history.
5. **notifications**: delete only **read** rows older than **90d**; unread badge/list must keep unread forever until marked read.

---

### Table A — `odds_snapshots` readers

| consumer | file:line | access pattern | history depth needed |
|----------|-----------|----------------|----------------------|
| Market candles | `api/v1/market_candles.py:45-49` | newest `points*2` ticks (points 10–500) | **~last 1k ticks** (hours–days at poll cadence), not multi-month HF |
| Market history (daily) | `api/v1/market_candles.py:111-127` | all ticks with `captured_at >= now-days` | **≤30d** full series (`days` query max 30) |
| Latest price | `api/v1/market_candles.py:89-93` | newest 1 | **latest only** |
| Edge history | `api/v1/edge_history.py:74-79` | all snapshots ascending for as-of join to predictions in window | window via `_resolve_window_hours` → **max 30d** (`alerts_feed.py:42`); daily close OK outside recent band if prediction still has as-of price |
| Orders live mid | `api/v1/orders.py:112-118` | newest non-seed/fallback | **latest only** |
| Portfolio marks | `api/v1/portfolio.py:64-76` | max(captured_at) per slug + join | **latest only** |
| WS price | `api/v1/ws.py:56-58` | newest 1 | **latest only** |
| Briefs snapshot meta | `api/v1/briefs.py:300-302` | newest 1 | **latest only** |
| MarketService latest / recent | `services/market_service.py:425-459` | latest subquery; optional cutoff window for “recent” | **latest + short recent cutoff** (UI deltas) |
| Live price tick | `services/live_price_tick.py:102-111` | window rank per slug newest | **latest only** |
| Signals screeners | `services/signals_service.py:165-172` | `captured_at >= now - lookback_hours` (default **168h = 7d**) | **≤7d** full series (configurable lookback) |
| Daily brief price | `services/daily_brief.py:47-49` | newest 1 | **latest only** |
| Research digest price-at | `services/research_digest_service.py:52-54` | at-or-before timestamp | **as-of any digest day** — daily close sufficient for old days |
| Daily digest moves | `workers/daily_digest.py:131-134` | newest 2 | **latest 2** |
| Price feed worker | `workers/price_feed_worker.py:62-64,173-175,252-256` | latest + idempotent insert by bucket | **latest + write path** (not a long reader) |
| Agent price tool | `agents/tools.py:129-132` | newest 500 then filter hours (default 24) | **≤24h** (cap 500 ticks) |
| Analyst agent mid | `agents/analyst.py:94-96` | newest 1 | **latest only** |
| News lag | `signals/news_lag.py:118-130` | latest / at-or-before | **latest + as-of event time** (event-local, hours) |
| Claim scorer (T08) | `eval/claim_scorer.py:68-94` | at-or-before claim; in `(created, horizon]` | **full ticks for claim→horizon** (default 60m; pending claims only) — **SCORING WINDOW — DO NOT PRUNE** |
| Clone leaderboard grade | `services/clone_leaderboard_service.py:122-151` | same as claim scorer | **full ticks for run→horizon (60m)** — **SCORING WINDOW** |
| Eval closing implied | `eval/service.py:68-81` | walk newest pre-close; FK fallback via `odds_snapshot_id` | **last pre-close forever + any FK-linked row** — **CLV/SCORING — NEVER DELETE LINKED** |
| Snapshot dataset (ML) | `ml/snapshot_dataset.py:12-19` | all snapshots on RESOLVED markets ordered | **historical series**; **daily closes OK** for old data |
| Backtest replay | `backtesting/snapshot_replay.py:128-167` | series in `[start,end]` / at-or-before | **historical series**; **daily closes OK** long-term |
| Live/seed helpers | `services/live_snapshot_seed.py:26`, `price_snapshot_seed.py:34,65-67` | existence / seed latest | **write/seed** not long-read |
| Snapshot persist | `data/snapshots.py:86-90` | dedupe by slug/source/captured_at | **write path** |
| Admin / smoke (scripts) | `scripts/smoke_live_markets.py:57-58` | latest by source | ops only |

**odds_snapshots R2 recommendation (from audit):**

| knob | default | rationale |
|------|---------|-----------|
| `DATA_RETENTION_ENABLED` | true | master flag |
| `ODDS_SNAPSHOT_FULL_RES_DAYS` | **90** | generous > max API history (30d), screeners (7d), edge (30d); covers scoring horizons with huge margin |
| Beyond full-res | **downsample** → keep last tick per (`market_slug`,`source`, UTC day) | candles long-term / ML / backtest / edge as-of |
| Protected IDs | never delete `id IN (SELECT odds_snapshot_id FROM prediction_logs WHERE odds_snapshot_id IS NOT NULL)` | FK + CLV fallback |
| Protected window | never delete/downsample rows with `captured_at >= now - full_res_days` | scoring/CLV recent windows |

---

### Table B — `signal_events` readers

| consumer | file:line | access pattern | history depth needed |
|----------|-----------|----------------|----------------------|
| Activity list | `api/v1/activity.py:111-116` | newest first, limit 1–200, offset | **recent pages** (~days of activity) |
| Alerts feed | `api/v1/alerts_feed.py:131-142` | alert families, optional `since`, limit | **since or recent**; digest max **30d** |
| Alerts digest | `api/v1/alerts_feed.py:284-289` | families + `created_at >= since` | **≤30d** (`_DIGEST_WINDOW_MAX_HOURS`) |
| Categories signal count | `api/v1/categories.py:57,109-113` | count since **7d** | **7d** |
| Feed unified | `api/v1/feed.py:230-232` | newest 200 | **recent only** |
| Desk latest signals | `api/v1/desk.py:112-115` | newest N for slug | **recent only** |
| Home (via alerts builder) | `api/v1/home.py:6-8,34-38` | top-N alert family | **recent / digest window** |
| Sports results | `api/v1/sports.py:223-224` | by signal_type | operational recent |
| Admin stats count | `api/v1/admin_stats.py:132` | COUNT(*) | any age (metric only) |
| Forecast dashboard CLV track | `services/forecast_dashboard_service.py:79-92,112` | newest scan_limit, filter resolved tracking in payload | **recent resolved signals** (limit-bound scan up to 10k rows) — 30d prune OK if old CLV already consumed/recorded elsewhere |
| Daily brief signals | `services/daily_brief.py:59-61` | newest per type for slug | **latest** |
| Research digest counts | `services/research_digest_service.py:120-127` | count since day_start | **≤1d** |
| Analyst agent deltas | `agents/analyst.py:118-148` | newest payload per delta type | **latest** |
| Citation audit | `eval/citation_audit.py:49-56` | existence of signal_type before brief.created_at | **lifetime of brief for audit** — risk if briefs older than prune; audit is post-hoc T08, not live trading. **Note:** 30d may mark old briefs “suspect” if signals pruned; acceptable vs DB growth (document); do not keep unbounded for this alone |
| Hygiene orphan/rewrite | `data_quality/hygiene.py:74-75,111-112` | recent ordered | **recent ops** |
| Diff/alignment/instability writers | `signals/diff_engine.py`, `alignment.py`, `instability.py` | INSERT | writers |
| Worker scans | `workers/tasks.py:412-447` | lookback cutoffs for mispricing/unusual flow | **hours** (config windows) |

**signal_events R2 recommendation:**

| knob | default | rationale |
|------|---------|-----------|
| `SIGNAL_EVENT_RETENTION_DAYS` | **30** | GOAL default; = digest max window; feeds are LIMIT DESC |
| Delete | `created_at < now - days` batched | idempotent |

---

### Table C — `notifications` readers

| consumer | file:line | access pattern | history depth needed |
|----------|-----------|----------------|----------------------|
| List + unread badge | `services/notification_service.py:141-166` | user-scoped, newest first, limit/offset; unread_count where `read_at IS NULL` | **unread: forever until read**; read history: UX only |
| Mark one / mark all | `notification_service.py:175-202` | by id / all unread | same |
| API list/read | `api/v1/notifications.py:83-150` | thin wrapper on service | same |
| Daily digest dedupe | `workers/daily_digest.py:50-53` | exists same user+type+title | **same calendar day** |
| Producers | `services/notification_producers.py` | INSERT | writers |

**notifications R2 recommendation:**

| knob | default | rationale |
|------|---------|-----------|
| `NOTIFICATION_RETENTION_DAYS` | **90** | GOAL default |
| Delete predicate | `read_at IS NOT NULL AND created_at < now - 90d` | **never delete unread** (badge correctness) |

---

### Writers (context only — not retention targets beyond their tables)

| table | primary writers |
|-------|-----------------|
| odds_snapshots | `data/snapshots.py`, `pipeline/ingest.py`, `workers/price_feed_worker.py`, seed services |
| signal_events | `signals/*`, `services/signals_service.py`, `signal_event_seed.py`, connectors |
| notifications | `notification_service.create_*`, `notification_producers`, `daily_digest` |

---

### R2 design sketch (do not implement until R1 committed)

- **ONE** module: `backend/app/workers/data_retention.py` (mirror `jobrun_retention.py`).
- Flag-gated generous defaults; batched idempotent deletes; JobRun heartbeat name **`data_retention`**.
- Dual-wire: in-process `_data_retention_loop` in `main.py` (pattern `_forecast_autolock_loop` / `_jobrun_retention_loop`) + ARQ `functions`/`cron_jobs` claim on `workers/tasks.py`.
- Register heartbeat in `_ALL_LOOPS` (`system.py`) + `LOOP_INTERVALS` (`loop_state.py`).
- Config knobs in `core/config.py` (no migration unless FK ON DELETE forces it — **prefer not**: delete only unreferenced odds rows).
- FOREIGN: `forecast_autolock.py`, `external_market*`, frontend, deploy.

---

## R2 — (pending)

## R3 — (pending)
