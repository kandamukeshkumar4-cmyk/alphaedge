# loop-v43-perf2 — STATE

| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| P1 | Market-detail short-TTL cache | DONE | `market_detail_cache.py` (10s TTL, success-only, slug-keyed); `/markets/{slug}/detail` public composition only; additive `cached`; `watching_count` may lag ≤10s (doc'd); watchlist mutations invalidate. Tests: hit/miss/expiry/error/cross-user. |
| P2 | Candles per-(slug,range) cache | IN PROGRESS | |
| P3 | Re-baseline + full gate | PENDING | |

## SHARED FILE CLAIMS
| File | Ticket | Status |
|---|---|---|
| backend/app/api/v1/market_detail.py | P1 | DONE — TTL cache wire-up |
| backend/app/schemas/market.py | P1 | DONE — additive `cached: bool = False` |
| backend/app/api/v1/watchlist.py | P1 | DONE — invalidate detail cache on add/remove |
| backend/app/api/v1/market_candles.py | P2 | claimed |

## LOOP LOG
- 2026-07-15 P1 DONE | market_detail_cache 10s success-only slug-keyed | watching_count lag documented; watchlist invalidate | tests hit/miss/expiry/error/cross-user | HEAD will be after commit
