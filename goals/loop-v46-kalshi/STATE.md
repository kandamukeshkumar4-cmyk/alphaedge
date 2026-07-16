# loop-v46-kalshi — STATE

## LOOP LOG

| ts (UTC) | ticket | status | notes |
|---|---|---|---|
| 2026-07-16T15:15Z | K1 | DONE | Real-ingest audit: skipped=200 is 100% board-join miss; commit `bea27a5` |
| 2026-07-16T15:20Z | K2 | DONE | Config-gated event-market fallback + raised caps; see K2 JUSTIFICATIONS |
| 2026-07-16T15:30Z | K3 | DONE | Tests + before/after + ruff green; full suite 1702 pass / 1 pre-existing foreign fail (not V46) |

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
| Filter loop | `backend/app/services/kalshi_live_ingest.py:60-133` (pre-K2) | hard cap, WC deferral, per-category cap, board join, upsert |
| Category map | `backend/app/services/kalshi_live_ingest.py:287-308` | raw Kalshi category → local tab |
| `skipped` counter | `backend/app/services/kalshi_live_ingest.py:104-110,133` (pre-K2) | **ONLY** increments on missing/empty board join |

### Important counter semantics

Production `skipped` does **not** count WC deferral, per-category full, hard-cap remainder, or missing tickers. V33 `skipped=200` = **200/200 board-join misses**.

### Real-ingest run (K1 harness)

Harness: `goals/loop-v46-kalshi/evidence/local_kalshi_audit.py`  
Report: `goals/loop-v46-kalshi/evidence/k1_audit_report.json`

```text
kalshi_open_events: imported=0  updated=0  skipped=200
reason_counts: no_markets_on_board=200  (100%)
join hit (8 pages / 8000 mkts): 0
join hit (20 pages / 20000 mkts): still 0
board sample: KXMVESPORTSMULTIGAMEEXTENDED-* volume_fp=0.00
per-event probe on misses: active markets exist (Elon Mars, NATO sec gen, Pope, …)
```

### Root cause (single)

**Events-first discovery + global board join against a multigame-dominated, truncated `/markets` cursor stream.** Intersection empty → every event increments `skipped`, nothing imported. Not a volume floor, category denylist, or dedupe.

### Evidence artifacts (K1)
- `goals/loop-v46-kalshi/evidence/local_kalshi_audit.py`
- `goals/loop-v46-kalshi/evidence/k1_audit_report.json`
- Commit: `bea27a5`

---

## K2 JUSTIFICATIONS — every relaxation

| change | default | justification from K1 | rejects junk? |
|---|---|---|---|
| `LIVE_KALSHI_EVENT_MARKET_FALLBACK=true` | **on** | Board join hit=0 forever; per-event `list_event_markets` returns genuine open/active contracts for the open-events list | Yes — still driven by `/events?status=open`, never walks multigame board alone |
| `LIVE_KALSHI_PER_CATEGORY_LIMIT` 6→**10** | 10 | Pre-K2 caps never engaged (0 picked). Slight widen after fix restores multi-category breadth vs ~24 catalog markets | Still hard-capped per mapped tab |
| `LIVE_KALSHI_MAX_MARKETS_PER_EVENT` 6→**8** | 8 | Multi-outcome events (NATO/Pope) truncated early; 8 still bounds ladder noise | Cap remains |
| `LIVE_KALSHI_MIN_EVENT_VOLUME=0` | 0 | No volume floor existed; long-horizon opens can be thin but tradeable. Floor available for ops | Ops can raise without code change |
| `LIVE_KALSHI_OPEN_EVENTS_LIMIT=200` | 200 | Config-gates the existing hardcode | — |
| SharedKalshiFetcher.`list_event_markets` | cache+429 | Needed for fallback without uncached N-fanout / raw 429 deaths | — |

### Explicit non-changes (honesty)
- Did **not** import the global board multigame flood (zero-liquidity parlays).
- Did **not** touch `normalize_kalshi_market` / resolution parsing (V14).
- Did **not** touch `external_market_bridge` (V33).
- Did **not** disable WC series deferral to `sync_world_cup_matches`.
- `PAPER_TRADING_ONLY` unchanged; no order path.

### Files touched (K2)
- `backend/app/core/config.py` — new LIVE_KALSHI_* knobs
- `backend/app/data/connectors/kalshi_fetcher.py` — `list_event_markets` + cache invalidate
- `backend/app/services/kalshi_live_ingest.py` — fallback join path + config wiring
- `backend/tests/test_kalshi_live_ingest.py` — filter tests

---

## K3 — tests, before/after, gate, verifier

### Before / after local real-ingest

| | imported | updated | skipped | catalog kalshi |
|---|---|---|---|---|
| **Before (K1 / V33)** | 0 | 0 | 200 | 0 |
| **After (K2 defaults)** | **266** | 0 | **0** | **266** |

Evidence: `goals/loop-v46-kalshi/evidence/k2_after_ingest.json`

By category after: Culture 46, Economics 58, Politics 57, Sports 59, Tech 26, Weather 20.  
Sample titles: Elon Mars, NATO Sec Gen outcomes, Next Pope — real open events with non-zero volume (e.g. Elon Mars volume=112572). No MVE multigame junk.

### Tests added (per changed filter)
- `test_open_events_board_join_miss_skips_without_fallback`
- `test_open_events_fallback_imports_when_board_misses`
- `test_open_events_board_hit_does_not_need_fallback`
- `test_open_events_min_event_volume_skips_thin_books`
- `test_open_events_per_category_limit`
- `test_open_events_max_markets_per_event_cap`
- `test_open_events_defers_wc_series`

Focused: **14 passed** (kalshi ingest + shared fetcher).

### Full gate

```text
ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q -p no:cacheprovider
→ 1702 passed, 28 skipped, 1 failed in 318s

FAILURE (PRE-EXISTING, FOREIGN — not introduced by V46):
  tests/test_live_tick_404_backoff.py::test_live_tick_demoted_skip_throttles_warn_when_still_open
  assert len(demoted_warns) == 1  (got 0)
  Reproduced on K1-only commit bea27a5 with no V46 code changes.
  Ownership: live_price_tick 404 backoff (loop V37 H1), not kalshi ingest.

uv run --extra dev ruff check app tests
→ All checks passed!
```

V46 delta vs suite: +7 tests, no weakened assertions.

### Fresh adversarial verifier (2026-07-16)

```text
VERDICT: PASS | Ship: YES

Guardrails: PAPER_TRADING_ONLY intact; no order path; no V14 normalize/resolution;
no V33 bridge; no frontend/deploy. Fallback is events-first + status=open
list_event_markets only; multigame board not walked alone. Knobs config-gated.

Claims match evidence: K1 skipped=200=100% board-join miss; K2 after imported=266
skipped=0 catalog=266; sample markets real/non-MVE. +7 filter tests present.

Non-blocking: min_event_volume default 0; no SharedKalshiFetcher.list_event_markets
unit test; 429 fan-out risk; 1 foreign live_tick test fail (V37, not V46).
```

Runner re-exec after verifier: ruff All checks passed; test_kalshi_live_ingest 9 passed.

---

## Notes / unrelated findings (not fixed)

1. **Pre-existing fail:** `test_live_tick_demoted_skip_throttles_warn_when_still_open` — demoted skip path returns correct status but caplog never sees "demoted skip" warning. Fails on clean `bea27a5`. Do not attribute to V46.
2. Kalshi 429s still fire during fallback fan-out; SharedKalshiFetcher backoff recovers (seen in after-run logs). Consider a small inter-call sleep later if ops sees incomplete fills under heavy rate limit — not blocking K2 (imported=266, skipped=0).
3. Board `max_pages=8` still wasteful when join is empty; left in place as cheap no-op join attempt + future-proof if Kalshi reorders the feed.

AutoLab: baseline=kalshi_open_events imported=0 skipped=200 | benchmark=local real-ingest catalog kalshi count + filter unit tests | iterations=1 (fallback+caps) best=imported=266 catalog=266 | budget=1/3 | outcome=improved
