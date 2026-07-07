# AlphaEdge improvement plans

Updated 2026-07-07. Plans 003–006 shipped; API image **kalshi4**.

## Status table

| # | Plan | Status | Depends on | Category |
|---|------|--------|------------|----------|
| 001 | Kalshi UI parity hero | DONE | API live | ui |
| 002 | Consolidate live-price hooks | PARTIAL (frontend-only; deferred — backend loop is out of scope here) | 001 | tech-debt |
| 003 | Extract `LivePriceTickService` from worker | **DONE** | — | tech-debt |
| 004 | Kalshi 429 backoff + shared event fetcher | **DONE** | 003 | perf |
| 005 | [Kalshi live API parity](005-kalshi-live-api-parity.md) | **DONE** | — | bug |
| 006 | [Seed snapshot on ingest](006-seed-snapshot-on-ingest.md) | **DONE** | 005 | bug |
| 007 | [Multiplex WS + poll budget](007-multiplex-ws-frontend-poll.md) | TODO | 005 | perf |
| 008 | [Retire/document hf_stage](008-retire-hf-stage-duplicate.md) | **DONE** | — | tech-debt |

## Recommended execution order

1. ~~**005**~~ — Kalshi candles/latest API
2. ~~**006**~~ — seed snapshot on ingest
3. **007** — frontend connection budget (execute next)
4. ~~**003**~~ — worker refactor (`LivePriceTickService` extracted)
5. **008** — duplication cleanup

## Plan 003 / 004 notes (shipped 2026-07-07)

- **003** — `LivePriceTickService` extracted into `backend/app/services/live_price_tick.py`;
  `run_live_tick_once` is now a thin wrapper that passes the worker's connector
  bindings to the service, so every existing caller and monkeypatch target keeps
  working. `persist_and_publish_tick` / `lapse_expired_markets` stay in the worker.
- **004** — `SharedKalshiFetcher` (`backend/app/data/connectors/kalshi_fetcher.py`)
  wraps `KalshiConnector` with exponential 429 backoff + a short-TTL in-memory
  cache for the event/board calls. `KalshiLiveIngestService` and the tick service
  both route Kalshi event/board calls through it; the tick's per-ticker board slice
  gets 429 backoff without a cache (fresh prices every tick).
- **002** — frontend-only hook consolidation (`useMarketPrice` / `live-prices.tsx` /
  `useLiveMarket`). Not implemented in this loop per the "do not touch frontend/"
  constraint; left PARTIAL.

## Deploy notes

| Surface | Image / URL |
|---------|-------------|
| API (2026-06-12) | `alphaedge-api:kalshi4` (006 seed on ingest + worker flatten fix) |
| Frontend | `https://proud-meadow-01b42b810.7.azurestaticapps.net` |

Verify after deploy:
```bash
curl "https://alphaedge-api.../api/v1/markets/ks-kxwcgame-26jun12canbih-can/candles?points=10"
# expect 200, source=live (not 404)
```

## Considered and rejected

- Split-flap / gamification price animations
- Copy Kalshi trademark logo

## Architecture verdict

| Area | Status |
|------|--------|
| Goals (phases 0–4, 6, X, Y, FIFA) | DONE in `goals/README.md` |
| Kalshi read API | **Fixed** (005 + kalshi3 deploy) |
| First-paint prices | **Fixed** (006 + kalshi4 deploy) |
| WS/poll fan-out | Gap → Plan 007 |
| `hf_stage/` duplicate | Gap → Plan 008 |

## AutoLab

```text
AutoLab: baseline=8 pass live tests (worker flatten bug pre-fix) | benchmark=14 pass live+kalshi tests | iterations=3 (006 seed + worker fix + test order_by) | budget=3/5 | outcome=improved
```
