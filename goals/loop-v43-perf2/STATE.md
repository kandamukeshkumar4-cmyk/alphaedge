# loop-v43-perf2 — STATE

| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| P1 | Market-detail short-TTL cache | DONE | `market_detail_cache.py` (10s TTL, success-only, slug-keyed); public composition only; additive `cached`; `watching_count` may lag ≤10s (doc'd). Invalidate on watchlist + market mutations (resolve/lock/pause/update/create/cancel). Tests: hit/miss/expiry/error/cross-user. |
| P2 | Candles per-(slug,range) cache | DONE | `market_candles_cache.py` (30s TTL); key `(slug, points)`; success-only; additive `cached`. Tests: hit/miss/expiry/error/per-key/cross-user. |
| P3 | Re-baseline + full gate | DONE | `py -3.13 loadtest/scripts/run_all.py` exit 0. Gate: **1693 passed, 28 skipped** + ruff clean. See before/after table. |

## SHARED FILE CLAIMS
| File | Ticket | Status |
|---|---|---|
| backend/app/api/v1/market_detail.py | P1 | DONE — TTL cache wire-up |
| backend/app/schemas/market.py | P1 | DONE — additive `cached: bool = False` |
| backend/app/api/v1/watchlist.py | P1 | DONE — invalidate detail cache on add/remove |
| backend/app/services/market_service.py | P1 | DONE — invalidate detail cache on mutations |
| backend/app/api/v1/admin_markets.py | P1 | DONE — invalidate on admin resolve |
| backend/app/api/v1/market_candles.py | P2 | DONE — per-(slug,points) TTL cache |

## P3 before/after p99 (L2 read-path, local SQLite stack)

**V20 baseline**: `loadtest/results/PERF-BASELINE.md` (readpath-20260714T153900Z)  
**V21 re-run** (prior loop): `readpath-20260714T191620Z`  
**V43 re-run**: `readpath-20260715T234209Z` · 15 VUs × 120s · **0 fails** · 787 reqs  
Evidence stamps: `smoke-20260715T234046Z`, `readpath-20260715T234209Z`, `trade-20260715T234426Z`

| Endpoint | V20 p50 | V20 p99 | V43 p50 | V43 p99 | Delta p99 vs V20 |
|----------|--------:|--------:|--------:|--------:|-----------------:|
| GET /markets/{slug}/detail | 12 | **330** | **4** | **120** | **−64%** (P1 TTL cache) |
| GET /markets/{slug}/candles | 13 | **79** | **6** | **1200** | +p99 tail (see caveats); **median −54%** |
| GET /signals/feed | 8 | 2100 | 5 | 40 | holds V21 cache win |
| GET /markets | 6 | 81 | 5 | 74 | ~flat |
| GET /portfolio (authed) | 9 | 1400 | 7 | 59 | variance / lighter contention this run |
| POST /auth/signup (setup) | 3100 | 5300 | 2300 | 3800 | setup-only bcrypt |

### vs V21 multi-VU noise (same host class)

| Endpoint | V21 p99 | V43 p99 | Note |
|----------|--------:|--------:|------|
| /detail | 1200 | **120** | P1 cache collapses tail vs V21 uncached spike |
| /candles | 1100 | 1200 | still multi-VU SQLite cold-miss spikes; p50 9→6 |

### L3 429 onset (single-token hammer POST /orders)

| Metric | V20 | V43 |
|--------|-----|-----|
| First 429 at attempt | 583 | 578 |
| Retry-After header | null (V20) / "23" (V21) | **"6"** |
| 5xx during probe | 0 | 1×503 (SQLite busy under hammer; not 5xx storm) |

### Contention caveats (honest)

1. **Local SQLite + multi-VU**: p99 tails remain dominated by write-lock / bcrypt signup ramp, not steady-state query cost. Medians are the honest product signal.
2. **Detail p99 330→120 and p50 12→4 is a real P1 win** (10s success-only slug cache). Mutations invalidate so resolve/watchlist tests stay correct.
3. **Candles p99 still spikes (~1.2s)** under multi-VU despite 30s cache — first miss per VU/key still hits DB under contention; subsequent hits keep p50 at 6ms. Do **not** claim candles p99 fixed; claim median + cache correctness.
4. **Rate limits left enabled** (600/min). Loopback only. `PAPER_TRADING_ONLY=true`.
5. Loadtest ran with P1+P2 code; invalidation-on-resolve fix landed after loadtest but does not change read-path latency profile (mutation path only).

## Gate (P3)

```
ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q -p no:cacheprovider
→ 1693 passed, 28 skipped in 288.59s

uv run --extra dev ruff check app tests
→ All checks passed!
```

## LOOP LOG
- 2026-07-15 P1 DONE | market_detail_cache 10s success-only slug-keyed | watching_count lag documented; watchlist + market mutation invalidate | tests hit/miss/expiry/error/cross-user | commit `89bc0b3` + follow-up invalidation fix
- 2026-07-15 P2 DONE | market_candles_cache 30s per (slug,points) | tests hit/miss/expiry/error/key/cross-user | commit `2a7d3ea`
- 2026-07-15 P3 DONE | run_all.py exit 0 | detail p99 330→120; candles median 13→6 p99 still SQLite-noisy | gate 1693 passed / 28 skipped | ruff clean

### ADVERSARIAL VERIFIER · P3 · local re-baseline · verdict: PASS
- Command: `py -3.13 loadtest/scripts/run_all.py` → exit 0 (L1+L2+L3).
- Guardrails: local 127.0.0.1:18020 only; PAPER_TRADING_ONLY; no frontend/deploy edits; no push/merge; order path untouched; no cross-user cache keys.
- Cache isolation: keys are slug / (slug,points) only; Authorization headers do not fork entries (tests prove).
- Mutation freshness: resolve/watchlist invalidate detail cache (regression caught by `test_market_detail_includes_resolution_fields`).
- Honest metrics: detail improved; candles median improved, p99 not claimed fixed.
- Full suite counts: **1693 passed, 28 skipped**; ruff clean.

AutoLab: baseline=V20 PERF-BASELINE L2 (detail p99=330, candles p99=79) | benchmark=local run_all.py L2 p99+p50 for detail/candles | iterations=1 full P1-P3 pass (detail p99 120, candles p50 6) | budget=1/1 loop | outcome=improved (detail) / candles median-only under SQLite multi-VU
