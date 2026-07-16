# loop-v46-kalshi — STATE

## LOOP LOG

| ts (UTC) | ticket | status | notes |
|---|---|---|---|
| 2026-07-16T15:15Z | K1 | DONE | Real-ingest audit: skipped=200 is 100% board-join miss; see K1 AUDIT below |
| — | K2 | PENDING | — |
| — | K3 | PENDING | — |

## SHARED FILE CLAIMS
(none)

---

## K1 AUDIT — kalshi_open_events skip quantification

### Path traced (production)

| step | file:line | what |
|---|---|---|
| Startup call | `backend/app/main.py:173` / `:584` | `KalshiLiveIngestService.sync_open_events()` |
| Open events list | `backend/app/data/connectors/kalshi.py:39-48` | `GET /events?status=open&limit=200` |
| Open board markets | `backend/app/data/connectors/kalshi.py:68-93` | `GET /markets?status=open` cursor pages, **default max_pages=8 → ≤8000 markets** |
| Fetcher cache/429 | `backend/app/data/connectors/kalshi_fetcher.py:93-123` | TTL cache + 429 backoff |
| Filter loop | `backend/app/services/kalshi_live_ingest.py:60-133` | hard cap, WC deferral, per-category cap, board join, upsert |
| Category map | `backend/app/services/kalshi_live_ingest.py:287-308` | raw Kalshi category → local tab |
| `skipped` counter | `backend/app/services/kalshi_live_ingest.py:104-110,133` | **ONLY** increments on missing/empty board join |

### Important counter semantics

Production `skipped` does **not** count:
- WC series deferral (`L95-96`, bare `continue`)
- per-category bucket full (`L99-100`, bare `continue`)
- hard-cap break remainder (`L90-91`, `break`)
- markets missing `ticker` (`L115-116`, bare `continue`)

V33's `skipped=200` therefore means **200/200 events failed the board join**, not "200 filtered by volume."

### Real-ingest run (K1 harness)

Harness: `goals/loop-v46-kalshi/evidence/local_kalshi_audit.py`  
Report: `goals/loop-v46-kalshi/evidence/k1_audit_report.json`  
Pattern: mirror of `goals/loop-v33-lockbreadth/evidence/local_funnel_run.py`  
`PAPER_TRADING_ONLY=true`, throwaway SQLite, real Kalshi trade-api read-only.

**Production path result (reproduced V33):**
```text
kalshi_open_events: imported=0  updated=0  skipped=200
catalog_kalshi_markets_after: 0
```

**Instrumented reason counts (identical filter order):**
```text
no_markets_on_board          200   ← 100% of production skipped
empty_markets_slice            0
picked_for_import              0
per_category_limit             0   (never reached — nothing picked)
wc_series_deferred             0
hard_cap_break_unexamined      0
empty_event_ticker             0
```

**Join diagnostics:**
```text
events fetched:              200
board markets (8 pages):    8000
board event_tickers:        6362
join hit:                      0
join miss:                   200
case_mismatch_only:            0
```

**Deeper pagination probe (20 pages = 20_000 markets, still cursor remaining):**
```text
board markets:           20000
board event_tickers:     14432
join hit vs top-200 events:  0   ← STILL ZERO
```

Board sample (first page) is **multigame sports parlays**, near-zero volume:
```text
ticker: KXMVESPORTSMULTIGAMEEXTENDED-S2026C344150C272-A83371AAA1A
event_ticker: KXMVESPORTSMULTIGAMEEXTENDED-S2026C344150C272
volume_fp: 0.00  last_price_dollars: 0.0000  yes_bid_dollars: 0.0000
```
Of first 500 board markets: only 14 had volume > 0; median volume = 0. Board markets have **no `category` field**.

**Per-event fetch probe on join-miss samples** (`list_event_markets`, `kalshi.py:110-118`):
| event_ticker | markets | status |
|---|---|---|
| KXELONMARS-99 | 1 | active |
| KXNEXTNATOSECGEN-99 | 8 | active |
| KXNEWPOPE-70 | 7 | active |
| KXWARMING-50 | 1 | active |
| KXMARSVRAIL-50 | 1 | active |

→ Markets for the open-events list **exist and are open/active**; they are simply **not present in the truncated global `/markets` board**, which is flooded by multigame extended sports products.

### What is NOT filtering (ruled out)

| hypothesized filter | verdict |
|---|---|
| Volume floor | **Not present** in `sync_open_events`. `_volume_usd` only stamps `Market.volume`. |
| Category denylist | Unmapped cats fall through to Culture (`L307-308`). Only Social/Transportation (1 each) unmapped in sample. |
| Dedupe fold | Fresh DB; imported=0 so no slug collisions. |
| Series filter | WC `KXWCGAME` deferral: 0 of the 200. |
| Expired/status | Events requested `status=open`; per-event markets return `active`. |
| Missing fields blocking upsert | Never reached upsert; join fails first. |

### Root cause (single)

**Events-first discovery + global board join against a multigame-dominated, truncated `/markets` cursor stream.**  
`list_open_events` returns long-horizon / series events (Elon Mars, NATO sec gen, …).  
`list_open_markets(max_pages=8)` returns ≤8000 rows dominated by `KXMVESPORTSMULTIGAMEEXTENDED-*` zero-liquidity parlays. Intersection of the two sets is **empty**, so every event increments `skipped` and nothing is imported.

The board join was introduced as a 429-avoidance optimization (`kalshi_live_ingest.py:75-77`); it accidentally zeroed the catalog path.

### Config knobs present today

- `LIVE_KALSHI_SERIES` (WC series only) — `config.py:304`
- No config for `per_category_limit` (hardcoded 6), `max_markets_per_event` (hardcoded 6), board `max_pages` (hardcoded 8), or join fallback.

### K2 direction (justified by this audit; implement AFTER this commit)

1. **Primary fix:** when board join misses for a category-eligible event, fall back to `list_event_markets(event_ticker)` via `SharedKalshiFetcher` 429 backoff — only for events that would otherwise be picked (bounded by category caps, not all 200).
2. **Config-gate** limits: `LIVE_KALSHI_PER_CATEGORY_LIMIT`, `LIVE_KALSHI_MAX_MARKETS_PER_EVENT`, `LIVE_KALSHI_EVENT_MARKET_FALLBACK`, optional min volume after fetch.
3. **Do not** import global-board multigame zero-liquidity junk as the widening strategy — that would flood the catalog with non-tradeable parlays.
4. **Do not** touch `normalize_kalshi_market` resolution parsing (V14) or the external_market_bridge (V33).

### Evidence artifacts
- `goals/loop-v46-kalshi/evidence/local_kalshi_audit.py`
- `goals/loop-v46-kalshi/evidence/k1_audit_report.json`
