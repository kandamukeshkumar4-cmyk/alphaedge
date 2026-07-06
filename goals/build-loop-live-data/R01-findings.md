# R01: Deployed Data-Path Audit — Findings

Audited 2026-07-06. Read-only trace of why the HF Space shows empty screens.

## TL;DR

The DB IS seeded on first boot (16 markets, 90 snapshots each), but:
1. Seed timestamps are anchored to 2026-06-02 — 34 days stale by today → charts
   filter them out or show a gap.
2. Live ingest (Kalshi + Polymarket) depends on external APIs being reachable
   from HF Space. If blocked/rate-limited, zero live markets are imported.
3. News/whale/weather/digest all need the ARQ worker + Redis → dead on HF Space.
4. Alignment triggers need ≥3 signal layers → analyst/briefs/eval never fire
   with only the price layer available.

## What works out of the box (no external deps)

- `seed_catalog_markets()` → 16 markets (NBA/Elections/FIFA/Crypto/Culture/Economics)
- `seed_price_snapshots()` → 90 OddsSnapshot rows per market (`source="seed"`)
- `seed_system_account()` → system paper-trading account
- `/api/v1/markets` → returns all 16 with `yes_price` from latest snapshot
- `_eval_loop` → `score_claims_task` + `analyst_aggregates_task` run in-process
- `lapse_expired_markets()` → runs in-process in the ingest loop

## What depends on external APIs

| Component | API | Behavior on failure |
|-----------|-----|---------------------|
| `_price_feed_loop` | Polymarket Gamma | Falls back to seed price; only 1/16 catalog markets |
| `_live_ingest_loop` | Kalshi REST + Polymarket Gamma | Catches exception, logs, retries every 5-30 min |
| `_live_tick_loop` | Both REST APIs | Only ticks imported live markets (empty set if ingest failed) |
| WebSocket streams | Kalshi/Polymarket WS | Additive; restart loop with 30s delay |

## What's dead without ARQ worker

- `news_scan_task` → `news_arrival` signal events
- `weather_scan_task` → `weather_edge` signal events
- `refresh_whales_task` / `snapshot_whale_positions_task` → whale tracking
- `morning_research_task` → daily digest briefs
- `wc2026_resolve_task` → auto-resolution (partially covered by `lapse_expired_markets`)

## The deepest bug: stale seed timestamps

`candle_seed.py` line 52: `_SEED_EPOCH = datetime(2026, 6, 2, 17, 0, 0, tzinfo=UTC)`

`seed_price_snapshots` calls `generate_candles(slug, 90, end_price, 3600)` with
no `now` arg → defaults to `_SEED_EPOCH`. The 90 candles span June 1–2, 2026.

If the frontend's chart component requests candles for "last 24h" or "last 7d",
the seed data is 34 days old and gets excluded → flat/empty chart.

**Fix**: Pass `now=datetime.now(UTC)` to `generate_candles` so seed data is
always "recent" on first boot. The `pad_candles()` function already exists for
backfilling gaps.

## Minimal fix list feeding R02–R08

| Ticket | Fix |
|--------|-----|
| R02 | Anchor seed candles to `now` instead of `_SEED_EPOCH`. Add more diverse markets (weather, sports betting lines, etc.) to reach ≥20. Label all as `source=seed`. |
| R03 | Candle endpoint must pad/backfill with seed data when real data is sparse. Frontend candle adapter must handle the `source=seed` label honestly. |
| R04 | Signals/CLV/arb endpoints: return 200 + empty shape on no data. Frontend: show "No data yet" instead of "API error". |
| R05 | Analyst: if market exists in catalog, use it; don't 404. Deterministic fallback brief when no LLM key. |
| R06 | Add in-process equivalents for critical ARQ tasks (news scan, weather scan at minimum). Lower alignment_min_layers to 1 when running without worker. |
| R07 | Smoke tests: assert markets ≥ 16, each has ≥ 30 snapshots, candles render non-flat. |
| R08 | Depends on R06 verdict. If in-process loops prove unreliable, add lightweight cron/endpoint. |
