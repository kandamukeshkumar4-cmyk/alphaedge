# AlphaEdge Backend Build Loop — "PolyScout" (AI Research Desk)

Author: Claude Fable 5 (principal engineer / product manager)
Executors: **Opus 4.8** (deep builder loop) + **Cursor** (verifier & mechanical loop)
Scope: **BACKEND ONLY.** No UI work in this loop — a separate UI loop document will follow.
Authored: 2026-07-02

---

## 0. Mission (read this first, every session)

Build the backend of the AI research desk on top of the existing AlphaEdge codebase:
real-time market streams → diff/trigger engine → whale tracker → AI analyst briefs
with citations → claim extraction → eval harness that publicly grades every AI claim
→ alerts → scheduled research loop → API endpoints that a future UI will consume.

You are NOT building from scratch. `backend/app` already contains: connectors
(Polymarket Gamma/CLOB, Kalshi REST, OddsAPI), snapshot store (`odds_snapshots`),
live ingest loops, a paper CLOB with `RiskService → OrderIntent → OrderBookService`,
XGBoost + calibration + walk-forward/CLV backtesting, LangGraph agents
(`agents/graph.py`), a news-signal pipeline, Brier/calibration evals, ARQ workers,
and 77 test files (all green). Extend it; do not duplicate it.

### Non-negotiable guardrails (violating any of these = stop and revert)
1. `PAPER_TRADING_ONLY=true` stays true everywhere. No wallets, no private keys,
   no real-money execution, no payment rails, no execution language.
2. The ONLY order path is `RiskService → validated OrderIntent → OrderBookService`.
   No agent or new service may submit orders any other way.
3. LLM/sentiment output is NEVER a trade trigger. It is features, briefs, and
   explanations only. (Sentiment tracks public money — the wrong side.)
4. Never game a benchmark or weaken a gate to make a metric pass.
5. Reference repos are TECHNIQUE SOURCES. Read them, reimplement the idea in our
   codebase style. NEVER vendor/copy their code wholesale, never copy their
   key-handling or live-execution code at all.
6. No mock/synthetic data in production paths (synthetic allowed inside tests only).

### Verification gate (run before every commit; a ticket is not DONE without it)
```
cd backend && uv run --extra dev pytest -q          # must pass (skips OK)
cd backend && uv run --extra dev ruff check app tests
```

---

## 1. Setup (one-time, before either loop starts)

1. Confirm baseline green: run the verification gate on a clean checkout of
   `codex/alphaedge-base`. If it is red, FIXING THE BASELINE IS TICKET ZERO —
   do nothing else first.
2. Create the state directory: `goals/build-loop/` containing:
   - `STATE.md` — the spine. Sections: `## Queue` (ticket table: id, title, status
     [QUEUED / CLAIMED-OPUS / CLAIMED-CURSOR / IN-REVIEW / DONE / BLOCKED],
     claimed_by, branch, last_update), `## Decisions log`, `## Blockers`,
     `## Metrics` (test count, latency numbers, Brier/CLV as they land).
   - One file per ticket `T01.md` … `T12.md` seeded from §3 of this document
     (copy the spec verbatim, then append progress notes under `## Progress`).
3. Reference repos: clone into `E:\polymarket clone\.reference\` (git-ignored;
   add `.reference/` to `.gitignore` if absent). Clone read-only, for study:
   - `Polymarket/agent-skills` — module boundaries, WS channel docs
   - `al1enjesus/polymarket-whales`, `NYTEMODEONLY/polyterm` — whale-alert patterns
   - `MrFadiAi/Polymarket-bot` — trader qualification math ONLY
   - `realfishsam/prediction-market-arbitrage-bot` — PM↔Kalshi matching reference
   - `aulekator/Polymarket-BTC-15-Minute-Trading-Bot` — fusion/weighted-voting +
     Prometheus patterns ONLY (ignore its strategies; never port martingale forks)
   - `Polymarket/agents`, `Polymarket/py-clob-client` — official API usage reference
   - `koala73/worldmonitor` — **AGPL-3.0: DO NOT CLONE into .reference, do not
     open its source. Ideas only, from README/docs** (instability-index concept,
     event-category taxonomy). Used by T13.
   - `ZhuLinsen/daily_stock_analysis` — MIT: patterns + code adaptation OK
     (daily push loop, channel formatting, provider fallback). NEVER port its
     stock TA strategies or any agent-places-order pattern. Used by T14.
4. Branch discipline: each ticket gets branch `loop/T{nn}-{slug}` off
   `codex/alphaedge-base`. Cursor mechanical chores use `loop/chore-{slug}`.
   Merge to base only after the ticket's acceptance gate + review pass.
5. External credentials note: Kalshi public WS and Polymarket public WS/data-api
   need NO keys for read access. If any ticket discovers a real external blocker
   (rate-limit ban, endpoint gone, missing key), write it to `## Blockers` in
   STATE.md with exact reproduction, mark ticket BLOCKED, and MOVE ON to the next
   ticket. Blockers pause tickets, never the loop.

---

## 2. Shared state protocol (both loops obey this)

- STATE.md is the single source of truth. The repo remembers; the model forgets.
- CLAIM before working: set status `CLAIMED-{OPUS|CURSOR}` + timestamp in STATE.md
  and commit that one-line change first. Never work an unclaimed ticket; never
  touch a ticket claimed by the other agent.
- After every meaningful step (design decided, file landed, tests green, gate run)
  append 1–3 lines to the ticket file `## Progress` and update STATE.md.
- Maker/checker split: the agent that built a ticket never approves it.
  Opus builds → Cursor verifies. Cursor's mechanical chores → Opus spot-checks.
- Commit style: small commits, message `T{nn}: <what>`, gate green before commit.
- Session start ritual (both agents): read STATE.md → read your claimed/next
  ticket file → read ONLY the source files that ticket names. Do not re-explore
  the whole repo each session.

---

## 3. The ticket queue (specs — copy each into its ticket file)

Order matters: T1→T4 build the nervous system, T5–T7 the intelligence,
T8 the proof, T9–T12 the product surface. T13–T14 are external-repo-inspired
add-ons (added 2026-07-02): T13 requires T03+T06 DONE, T14 requires T09+T10
DONE — claim them only when their dependencies are DONE; otherwise they wait at
the back of the queue. Do everything else in numeric order unless BLOCKED.

### T01 — Kalshi WebSocket stream connector
**Why:** the analyst agent must react in seconds; 5-min REST polling can't.
**Files:**
- `backend/app/data/streams/__init__.py`
- `backend/app/data/streams/base.py` — `StreamEvent` dataclass (market_slug,
  kind: `tick|orderbook_delta`, payload, source, exchange_ts, received_ts) +
  abstract `MarketStream` (async `run(callback)`, reconnect w/ jittered backoff
  1s→60s cap, heartbeat timeout 30s, resubscribe-on-reconnect, connection-state
  property).
- `backend/app/data/streams/kalshi_ws.py` — public Kalshi WS
  (`wss://api.elections.kalshi.com/trade-api/ws/v2`), subscribe `ticker_v2` +
  `orderbook_delta` for all mirrored `ks-*` market tickers (look them up from the
  Market table via existing `kalshi_live_ingest` naming). Normalize to StreamEvent.
- Wire-in: `backend/app/main.py` — when `settings.live_feed_enabled`, start the
  stream task alongside the existing `_live_ingest_loop`; the callback feeds the
  SAME tick path `price_feed_worker` uses (publish to WS hub + epsilon-persist to
  `odds_snapshots`). REST polling stays as discovery + fallback when stream is down.
- Config: `core/config.py` — `kalshi_ws_enabled`, `stream_reconnect_max_sec`.
**Tests** (`backend/tests/test_kalshi_ws.py`): parse recorded fixture frames
(ticker + orderbook delta + heartbeat) → correct StreamEvents; reconnect logic via
fake socket that dies twice; malformed frame → logged + skipped, never crashes;
no regression in `test_ws_prices.py`.
**Accept:** with fixtures, exchange_ts→hub-publish measured in test < 50ms;
service degrades to polling when WS unavailable. **Reference:** Kalshi WS docs +
`Polymarket/agent-skills` websocket module for structure.

### T02 — Polymarket CLOB WebSocket stream
**Files:** `backend/app/data/streams/polymarket_ws.py` — market channel
`wss://ws-subscriptions-clob.polymarket.com/ws/market`, subscribe by asset ids of
mirrored `pm-*` markets (asset/token ids from existing Gamma connector payloads —
extend `live_market_ingest` to persist `clob_token_ids` into Market metadata if
missing: that sub-change belongs to this ticket). Normalize `price_change` /
`book` messages to StreamEvent. Same reconnect contract as T01 (inherit base).
**Tests:** `test_polymarket_ws.py`, fixture frames, same pattern as T01.
**Accept:** both streams run concurrently in main.py; a kill of one does not
affect the other.

### T03 — Snapshot diff engine
**Why:** Hermes insight — "watch the changes, not the state." We store state today
but never diff it.
**Files:** `backend/app/signals/diff_engine.py` — pure functions + one service:
`compute_market_delta(prev: MarketSnapshotState, curr) -> list[DeltaEvent]`.
DeltaEvent kinds: `price_jump` (|Δimplied_yes| ≥ configurable bps within window),
`orderbook_flip` (bid_size/ask_size ratio crosses threshold), `volume_surge`,
`news_arrival` (from T06), `whale_delta` (from T05). Persist to existing
`signal_events` table (type=`delta:*`), publish on the existing DomainEventBus.
State snapshots per market kept in Redis (existing session/redis infra) keyed
`diff:{slug}`, TTL 1h.
**Tests:** `test_diff_engine.py` — threshold boundaries (exactly-at threshold does
NOT fire; strictly-over fires), no-prev-snapshot → no event + state seeded,
idempotent on identical snapshots.
**Accept:** stream ticks from T01/T02 flow through the diff engine in main.py.

### T04 — Alignment scorer (the trigger)
**Why:** fire the analyst only on high-conviction moments; 1 layer = noise,
≥3/4 layers = signal (Hermes alignment test).
**Files:** `backend/app/signals/alignment.py` — rolling 10-min window per market
over DeltaEvents; layers = {price/orderbook, whale, news, model-edge (call
existing `forecasting/predictor.py` — cached, never train in the hot path)}.
`AlignmentScore(market_slug, layers_firing: set, direction, score 0–4, window)`.
Score ≥ 3 → emit `signal_events` type=`alignment` + DomainEvent `analyst.trigger`.
Config thresholds in `core/config.py`. Add a fusion-style per-layer weight dict
(default 1.0 each) so weights are tunable later (aulekator fusion pattern) — but
NO self-learning weight updates in this ticket.
**Tests:** `test_alignment.py` — 2 layers → no trigger; 3 layers same direction →
trigger; 3 layers mixed direction → no trigger; window expiry resets.
**Accept:** end-to-end test: fixture tick + whale + news events → one
`analyst.trigger` event, exactly once (dedupe within window).

### T05 — Whale tracker (Polymarket data-api)
**Why:** #1 addable edge per research; our `onchain.py` is a stub — retire it.
**Files:**
- `backend/app/data/connectors/polymarket_data_api.py` — REST
  (`https://data-api.polymarket.com`): leaderboards, `/positions?user=`,
  `/trades?user=`. httpx + tenacity retries + timeouts, same style as existing
  connectors. No auth needed.
- `backend/app/signals/smart_money.py` (extend, don't replace) — qualification:
  ≥50 resolved markets AND ≥65% accuracy AND ≥1.5 profit factor AND
  not-one-hit-wonder (top single win < 40% of total PnL) (MrFadiAi math,
  reimplemented). Snapshot qualified wallets' positions each cycle; **diff deltas**
  (adds/exits/flips) → DeltaEvent kind `whale_delta` into T03.
- `backend/app/services/wallet_service.py` (extend) — refresh-leaderboard job,
  weekly re-qualification.
- DB (`db/models.py` + one Alembic migration `023_wallet_tracking.py`):
  `tracked_wallets(address pk, accuracy, resolved_count, profit_factor,
  qualified bool, qualified_at, meta json)`,
  `wallet_position_snapshots(id, address fk, market_slug, size, avg_price,
  captured_at)` with index (address, market_slug, captured_at).
- Worker: `workers/tasks.py` — `refresh_whales_task` (leaderboard weekly),
  `snapshot_whale_positions_task` (every 3 min via ARQ cron).
- Delete `data/connectors/onchain.py` and its references (it is a stub).
**Tests:** `test_polymarket_data_api.py` (fixture payloads), `test_whale_qualification.py`
(each rule's boundary + the one-hit-wonder exclusion), `test_whale_deltas.py`
(add/exit/flip detection, no delta on unchanged).
**Accept:** with fixtures, a qualified wallet adding size produces a `whale_delta`
that reaches the alignment scorer.

### T06 — News→price lag detector
**Why:** headline lands, market hasn't repriced → the analyst's best moment.
**Files:** `backend/app/signals/news_lag.py` — consume existing `news_signal`
pipeline output (it already tags markets); compare news timestamp vs price
movement since (from `odds_snapshots` ticks): if |Δprice| < threshold within
`lag_window_sec` (default 300s) after a high-relevance headline → DeltaEvent
`news_arrival(unpriced=True)`. Sentiment from the news pipeline is metadata on
the event, never a standalone trigger (guardrail 3).
**Tests:** `test_news_lag.py` — priced-in headline → no event; unpriced → event;
stale headline (>window) → no event.

### T07 — Analyst agent (the flagship)
**Why:** the product. Trigger → evidence → cited brief → falsifiable claim.
**Files:**
- `backend/app/agents/analyst.py` — LangGraph graph (mirror `agents/graph.py`
  conventions incl. optional-import fallback): nodes
  `gather_market_state` (snapshot, recent ticks, orderbook) →
  `gather_evidence` (news items w/ URLs, whale deltas w/ addresses+history, model
  probability + edge from predictor) → `write_brief` (LLM; uses the existing LLM
  layer/judge config; strict output schema) → `extract_claim` → `persist_publish`.
- Brief schema (pydantic, `schemas/brief.py`): market_slug, trigger_event_id,
  headline (≤120 chars), body_markdown (≤1200 chars), citations
  `list[{kind: news|wallet|model|orderbook, ref, url?}]` (MINIMUM 1 or the brief
  is rejected), claim `{direction: up|down|justified|overreaction,
  horizon_minutes: 60|1440, confidence: 0–1}`, model_version, prompt_version,
  latency_ms, created_at.
- DB migration `024_briefs.py`: `analyst_briefs` table (+ index market_slug,
  created_at) and `brief_claims` (brief fk, claim fields, status
  pending|correct|incorrect|void, resolved_at, resolution_price).
- Trigger wiring: DomainEventBus subscriber on `analyst.trigger` → run graph
  async; per-market cooldown (default 15 min) so one market can't spam.
- Publish: existing WS hub channel `briefs` + persist.
- LLM unavailable (no key) → deterministic template brief from structured
  evidence, flagged `generator: fallback` (system must run without any LLM key).
**Tests:** `test_analyst_agent.py` — graph runs on fixture evidence with fallback
generator; citation-required rejection; cooldown; claim always parseable.
`test_briefs_persist.py` — schema roundtrip.
**Accept:** fixture trigger → persisted brief with ≥1 citation and a claim, in
one async flow; measured graph latency logged.

### T08 — Eval harness (the hire-signal; do NOT cut corners here)
**Why:** every claim gets graded by reality. This is the public track record.
**Files:**
- `backend/app/eval/claim_scorer.py` — for each pending `brief_claims` row past
  its horizon: fetch price at claim time + at horizon from `odds_snapshots`;
  `up/down` correct iff moved ≥ epsilon in direction; `justified` correct iff no
  reversion beyond epsilon; `overreaction` correct iff reversion ≥ epsilon;
  insufficient snapshot data → `void`, never guessed.
- `backend/app/eval/analyst_metrics.py` — accuracy by category / claim-type /
  model_version / prompt_version, rolling windows (7/30/all), Brier for
  confidence calibration of claims, sample counts with `provisional` flag when
  n < 30. Persist aggregates (extend `eval_aggregates` or new
  `analyst_eval_aggregates` via migration `025`).
- Citation-faithfulness audit: `eval/citation_audit.py` — sampled check that each
  cited news ref existed before brief.created_at (no post-hoc citations) and
  cited wallet deltas exist in `wallet_position_snapshots`. Structural audit only
  — no LLM needed.
- Worker: `score_claims_task` (ARQ, every 15 min), `analyst_aggregates_task`
  (hourly).
**Tests:** `test_claim_scorer.py` — every claim type × correct/incorrect/void
matrix (12 cases minimum), epsilon boundaries, no-lookahead (scorer may only read
snapshots ≤ horizon time — negative-control test that FAILS if future data used).
`test_analyst_metrics.py` — aggregates on fixture history; provisional flag.
**Accept:** seeded fixture briefs → deterministic accuracy numbers reproduced.

### T09 — Alert dispatch
**Files:** `backend/app/services/alert_dispatch.py` — subscriber on `alignment`
and new-brief events → write `alerts` table (exists) + push WS hub channel
`alerts` + optional Telegram (bot token from settings; feature-flagged OFF by
default; message ≤ 400 chars, phone-readable) + optional generic webhook URL.
**Tests:** `test_alert_dispatch.py` — fan-out on fixture events; disabled flags →
no external calls (assert via mock transport); dedupe per event id.

### T10 — Scheduled research loop (Minara loop-1 pattern, ours)
**Files:** `workers/tasks.py` — `morning_research_task` (ARQ cron, daily):
pick top-N markets by 24h movement + open interest → run analyst graph on each
(respecting cooldowns) → write a digest row (`analyst_briefs` with
kind=`digest`) summarizing: new briefs, claim scoreboard changes, top unpriced
news, whale activity. This is "the desk runs while you sleep."
**Tests:** `test_morning_research.py` — selection logic (top-N by movement),
digest assembled from fixtures, idempotent per day.

### T11 — Model upgrade: LightGBM primary + SHAP explanations (AutoLab ticket)
**Why:** quant depth + per-prediction "why" the briefs can cite.
**Files:** `ml/trainer.py` — model registry entry `lightgbm` (dep add to
pyproject `[extra]`), same walk-forward/calibration path as XGBoost; artifact
versioning already exists — use it. `ml/explain.py` — SHAP top-5 features per
prediction, persisted into `prediction_logs` (new json column via migration
`026`). `forecasting/predictor.py` — include top features in ForecastPrediction
so T07's evidence node can cite them.
**AutoLab protocol:** baseline = current XGBoost walk-forward Brier/CLV on the
recorded snapshot dataset (measure FIRST, write to STATE.md `## Metrics`);
benchmark command = the walk-forward eval; budget = 10 iterations, K=3
no-progress → stop and keep best. Never worse than baseline ships.
**Tests:** `test_lightgbm_trainer.py`, `test_shap_explain.py` (deterministic on
fixture model), all existing ml tests stay green.
**Accept:** AutoLab line recorded in STATE.md:
`AutoLab: baseline=<brier> | benchmark=walk_forward | iterations=<n+best> | budget=<used/10> | outcome=<...>`.

### T12 — Public API for the future UI
**Files:** `backend/app/api/v1/briefs.py` — `GET /api/v1/briefs` (paginated feed,
filter market/category/kind), `GET /api/v1/briefs/{id}`,
`GET /api/v1/analyst/track-record` (aggregates from T08, incl. per-version),
`GET /api/v1/analyst/track-record/claims` (paginated graded claims —
transparency), `GET /api/v1/markets/{slug}/latency` (stream health/latency
badge data). Rate-limited via existing slowapi middleware; response schemas in
`schemas/`; register router in main.py.
**Tests:** `test_briefs_api.py` — pagination, filters, empty states, rate limit
header presence, no auth required for reads.
**Accept:** OpenAPI docs render all new endpoints; this is the UI-loop contract.

### T13 — Instability & event-category signal (worldmonitor-inspired; clean-room)
**Why:** election/geopolitics markets have no structured macro feature today;
worldmonitor's Country Instability Index shows the shape that works.
**License rule (hard):** `koala73/worldmonitor` is AGPL-3.0. Do NOT clone it,
do NOT read its source files. Only its public README/feature description may
inform this ticket. Everything here is implemented from scratch in our style.
**Depends on:** T03 + T06 DONE (do not claim before).
**Files:**
- `backend/app/signals/event_taxonomy.py` — fixed enum of event categories
  (military, elections, cyber, energy, economy, courts/legal, health, climate,
  unrest, diplomacy, tech, finance, sports-external, crime, other) + a
  classifier that tags each `news_signal` item: keyword/rule-based first, LLM
  refinement only if the LLM layer is configured (fallback = rules only).
- `backend/app/signals/instability.py` — per-region rolling score (0–100):
  weighted count of tagged high-severity items in a 24h window, decayed;
  regions = the country/region tags the news pipeline already extracts (extend
  extraction if missing — that sub-change belongs to this ticket). Persist to
  `signal_events` (type=`instability`), publish DeltaEvent kind
  `instability_shift` into the T03 diff engine when score crosses configurable
  thresholds.
- Feature wiring: `forecasting` feature builder gains `instability_score` +
  `event_category_counts` features for election/geopolitics-class markets ONLY,
  behind config flag `instability_feature_enabled` (default false).
- Config: `core/config.py` — flag + thresholds + window.
**Tests:** `test_event_taxonomy.py` (rule classifier on fixture headlines,
unknown → `other`, never crashes), `test_instability.py` (decay math, threshold
boundary exactly-at does not fire, no-news region → score 0),
`test_instability_feature.py` (flag off → features absent; on → present, NBA
markets never get them).
**AutoLab protocol (gates the flag, not the code):** baseline = walk-forward
Brier/CLV on election-class markets with flag off (measure FIRST → STATE.md
`## Metrics`); benchmark = same eval with flag on; budget 8 iterations, K=3.
Flag ships default-ON only if measurably better; otherwise merge code with flag
OFF and record `outcome=stalled`.
**Accept:** fixture news items → tagged categories → region score → DeltaEvent
reaches alignment scorer as a layer contribution; AutoLab line in STATE.md.

### T14 — Daily brief distribution (daily_stock_analysis-inspired)
**Why:** "the desk runs while you sleep" needs a delivery surface; MIT-licensed
`ZhuLinsen/daily_stock_analysis` has the proven shape (daily LLM dashboard →
Discord/Telegram push).
**License rule:** MIT — adapting patterns/code is allowed WITH attribution in
the file docstring. Explicitly banned imports: its stock TA strategies, and any
pattern where the agent acts on a market (guardrails 2/3 unchanged: LLM output
is briefs only, never a trade trigger).
**Depends on:** T09 + T10 DONE (do not claim before).
**Files:**
- `backend/app/services/daily_brief.py` — assemble the T10 digest into a
  channel-ready daily brief: per tracked market — live price, model prob, edge,
  CLV-gate status, top news driver, whale activity line; plus claim-scoreboard
  delta from T08. Pure assembly from existing tables; no new analysis.
- Formatters: `daily_brief_markdown()` (web/WS), `daily_brief_compact()`
  (≤4000 chars, Telegram/Discord-safe) — port the channel-formatting idea, not
  the code wholesale.
- Dispatch: reuse T09 `alert_dispatch` channels (WS `briefs` channel + Telegram
  + generic webhook), all external pushes feature-flagged OFF by default.
  Provider-fallback chain pattern: if LLM narrative unavailable → deterministic
  template (same fallback contract as T07).
- Worker: hook into T10's `morning_research_task` (extend, don't duplicate the
  cron) — digest row gains `distribution` metadata (channels attempted/sent).
**Tests:** `test_daily_brief.py` — assembly from fixture rows (deterministic
output), compact format length cap, empty-day brief still valid, flags off →
zero external calls (mock transport assert), idempotent per day.
**Accept:** fixture day → one brief assembled + dispatched to WS, external
channels only when flagged; no order-path code touched (grep-verifiable).

### Chore backlog (Cursor-owned, parallel, any time)
- C1: consolidate `PaperOrder` vs `Order` — investigate usage, migrate + drop the
  legacy one (needs Opus sign-off on the migration plan before executing).
- C2: fold `PaperSignal` semantics into `signal_events` where duplicated.
- C3: add `/metrics` Prometheus endpoint (counters: stream events/s, briefs
  generated, claims scored, WS clients) — aulekator observability pattern.
- C4: fixture-recording script `backend/scripts/record_ws_fixtures.py`.
- C5: keep `explorer-notes.md` + README architecture section current as tickets land.

---

## 4. LOOP A — Opus 4.8 (deep builder)

Paste this as Opus's standing instruction / `/goal`:

```text
GOAL: work docs/project/BUILD_LOOP_BACKEND.md ticket queue T01→T14 to DONE.
(T13 waits for T03+T06; T14 waits for T09+T10 — skip them until eligible.)
Stop-condition: every ticket in goals/build-loop/STATE.md is DONE or BLOCKED-
with-a-written-external-blocker. Do not stop for any other reason. Do not ask
questions a file could answer.

EVERY ITERATION (one ticket per iteration):
1. READ goals/build-loop/STATE.md, claim the lowest-numbered QUEUED ticket
   (status CLAIMED-OPUS, commit the claim). Read the ticket file and ONLY the
   source files it names.
2. THINK FROM SCRATCH (before any code): from first principles — what must be
   true here, what are the real constraints (async event loop, Postgres, Redis,
   ARQ, existing DomainEventBus, PAPER_TRADING_ONLY)? Don't pattern-match to the
   reference repo's solution; derive ours, and write the 5–10 line design
   rationale into the ticket file under ## Design BEFORE implementing. If the
   obvious approach treats a symptom, find the root cause and note it.
3. IMPLEMENT exactly the files the ticket names, in repo style (httpx+tenacity,
   pydantic schemas, service classes, Alembic migrations). Small commits on
   branch loop/T{nn}-{slug}. Tests are part of implementation, not after.
4. BREAK WHAT YOU BUILT, IN PARALLEL: spawn subagents, each attacking from one
   angle only — hostile input (malformed WS frames, absurd payloads, unicode
   slugs), careless operator (service restarts mid-stream, Redis flushed, DB
   migration half-applied), performance (1000 markets, burst of 10k events,
   memory growth over 24h simulated), concurrency/async (double-trigger, task
   cancellation, reconnect storm). Merge findings into one list in the ticket
   file, worst first, each with exact trigger. Fix everything worst-first; add
   a regression test per real hole. Do not defend the code — attack it.
5. GATE: run the full verification gate. Green → status IN-REVIEW in STATE.md,
   append handoff note for Cursor. Red → fix; if 3 consecutive iterations make
   no progress, write reorganization note and either de-scope to the ticket's
   acceptance minimum or mark BLOCKED with evidence. Never hand off worse than
   baseline.
6. UPDATE STATE.md (## Queue row, ## Metrics if measured, ## Decisions if any)
   and the ticket ## Progress. Then IMMEDIATELY claim the next ticket. While
   waiting on Cursor review of T(n), start T(n+1) — reviews must not idle you.
7. When Cursor posts review findings on one of your IN-REVIEW tickets:
   address CONFIRMED findings before merging that ticket to codex/alphaedge-base.
   You may not approve your own ticket.

STOP ONLY FOR: missing external credential/endpoint (write it to ## Blockers),
destructive ambiguity (a step would delete data / rewrite history), or a direct
conflict between this document and AGENTS.md guardrails (guardrails win — stop
and record). Everything else: decide, note the decision in STATE.md, continue.
```

---

## 5. LOOP B — Cursor (verifier + mechanical worker)

Paste this into Cursor (Fable/strong model as its agent, per-repo AGENTS.md is
already read automatically). Cursor NEVER builds T-tickets; it verifies them and
executes chores.

```text
GOAL: continuously (a) adversarially verify every ticket that reaches IN-REVIEW
in goals/build-loop/STATE.md, and (b) drain the Chore backlog (C1–C5) from
docs/project/BUILD_LOOP_BACKEND.md §3. Stop-condition: all tickets DONE/BLOCKED
and chore backlog empty. Otherwise loop forever; poll STATE.md each iteration.

EVERY ITERATION:
1. READ goals/build-loop/STATE.md.
2. IF any ticket is IN-REVIEW (priority over chores): claim the review (note
   "review: CURSOR" on the row). You are the checker; the maker's claims are
   unverified until you reproduce them. Do, in parallel subagents where possible:
   - re-run the full verification gate yourself from clean;
   - diff review against docs/project/BUILD_LOOP_BACKEND.md guardrails §0
     (order path untouched? no keys? no execution language? no vendored code?);
   - spec compliance: every file/test/acceptance bullet in the ticket spec
     exists and does what the spec says — check the tests actually assert the
     boundary cases named in the spec, not just happy paths;
   - one hostile pass of your own (different angle than the maker used — read
     their ## Break findings first and attack what they did NOT try).
   Verdict into the ticket file under ## Review: PASS (→ status DONE, maker
   merges) or FAIL with numbered CONFIRMED findings, each with exact trigger
   and file:line (→ status back to CLAIMED-OPUS). Never edit T-ticket code
   yourself; findings only.
3. ELSE IF chores remain: claim the next chore (CLAIMED-CURSOR), branch
   loop/chore-{slug}, implement mechanically and minimally (this is grunt work:
   no new abstractions, no scope growth), gate green, update STATE.md, and for
   C1/C2 (schema changes) require an Opus sign-off note in the chore section
   before running any migration.
4. ELSE: idle-check — re-run the gate on codex/alphaedge-base; if red, that is
   a P0: write it to ## Blockers with the failing output and flag the newest
   merged ticket as suspect.
5. UPDATE STATE.md every iteration, even if only "no work available, base green,
   {timestamp}".

STOP ONLY FOR the same three conditions as Loop A.
```

---

## 6. Finish line

When STATE.md shows T01–T14 DONE and chores drained, run the DEDICATED FINAL
REVIEW PASS (Opus and Cursor jointly, fresh eyes, whole-diff vs where we started):
architecture coherence, dead code, every guardrail, full gate, latency numbers
recorded in ## Metrics, README + explorer-notes updated. Deliverable of the loop:
a backend where `uvicorn app.main:app` + workers give you — live streamed prices,
alignment triggers, AI briefs with citations, publicly-graded claims, alerts, and
the /api/v1/briefs + /analyst/track-record endpoints the UI loop will consume.
Definition of done is the acceptance gates, not "it runs."

UI: explicitly OUT OF SCOPE here. A separate BUILD_LOOP_UI.md will consume T12's
API contract. Do not touch `frontend/` in this loop except C5 doc mentions.
