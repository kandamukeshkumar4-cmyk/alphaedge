# STATE105 — markets catalog pagination (backend) + audit blockers

**Branch:** `loop105-catalog/node`  
**Seat:** Cursor Grok 4.5 High (BACKEND)  
**Date:** 2026-07-24  
**Status:** DONE — PASS WITH FIXES blockers resolved (proof below)

## Bug confirmed (prior)

`backend/app/api/v1/routes.py` `list_markets` had no `limit`/`offset` params. FastAPI discarded
`?limit=` / `?offset=` query args; every call returned the full catalog.

## Implemented (exact contract — unchanged this pass)

1. `list_markets`: `limit: int = 100`, `offset: int = 0`; validate `1..500` / `offset >= 0` → 400.
2. Response shape unchanged: `list[MarketResponse]`.
3. Headers on every 200: `X-Total-Count`, `X-Page-Limit`, `X-Page-Offset`.
4. `MarketService.list_public_markets(*, …, limit=100, offset=0) -> tuple[list, int]` with SQL
   `LIMIT`/`OFFSET` + count-before-slice (not Python slice-after-fetch).
5. Cache key `(category, sort, q, limit, offset)` stores `(rows, total)`.

## Blocker fixes

### Blocker 1 — stable sort tiebreak

Appended `Market.id.desc()` as the final `order_by` key on every
`list_public_markets` branch (`active`, `traders`, `newest`, default/`volume`).

Test: `test_sort_ties_are_stable_across_page_boundary` in
`tests/test_loop105_markets_pagination.py`.

### Blocker 2 — explicit internal caller limits

| Caller | Limit chosen | Notes |
|--------|--------------|-------|
| `routes.py` `list_markets` | query `limit`/`offset` (default 100) | Public paginated contract; already explicit |
| `opportunities.py` | `limit=_MAX_CANDIDATES` (200) | Candidate pool must reach the 200 cap |
| `categories.py` | `limit=500`; `market_count = total` | Rows for opp scoring; count from service total |
| `home.py` | *(not edited)* | `markets_limit` Query cap ≤25; OK under default 100. Outside named API modules / budget law → **Noted, not fixed** |

### Failing-first verification (caller tests)

Both new tests in `tests/test_loop105_caller_limits.py` **FAILED** against pre-fix code, then **PASSED** after the fix:

```text
$ cd backend && uv run --extra dev pytest -q tests/test_loop105_caller_limits.py --basetemp=E:/polymarket-worktrees/loop105-catalog/.ptfail -vv
FAILED tests/test_loop105_caller_limits.py::test_opportunities_candidate_pool_not_truncated_by_default_limit
FAILED tests/test_loop105_caller_limits.py::test_category_market_count_reflects_total_not_page
============================== 2 failed in 9.22s ==============================
```

Literal assertion failures: opportunities `assert all(row["edge"] == 0.4 …)` → False;
category `assert body["market_count"] == n` → `assert 100 == 120`.

## Noted, not fixed

- `home.py:61` still calls `list_public_markets(sort="active")` without an explicit
  `limit=` — safe today (`markets_limit` ≤ 25) but would silently truncate if the
  home top-N ever exceeded the service default. Out of charter edit set
  (`opportunities.py` + `categories.py` only for API modules).
- `markets_cache.py` type annotations still describe the pre-pagination 3-tuple key /
  bare list value (runtime is correct). Auditor marked non-blocking.
- Prod catalog still huge; callers that need >500 rows must page.

## Authz / OpenAPI

Public contract unchanged → openapi snapshot must still pass unmodified (proof below).
Path set unchanged → no authz matrix edit.

## AutoLab

AutoLab: not applicable (no iterative measure) — one-shot audit blocker fix.

## NEEDS USER

(none)

---

## STOP CONDITION PROOF (pasted)

### Blocker fixes — pagination + caller tests

```text
$ cd backend && uv run --extra dev pytest -q tests/test_loop105_markets_pagination.py tests/test_loop105_caller_limits.py --basetemp=E:/polymarket-worktrees/loop105-catalog/.ptfix
............                                                             [100%]
12 passed in 9.36s
```

### Ruff

```text
$ cd backend && uv run --extra dev ruff check app tests
All checks passed!
```

### OpenAPI snapshot (contract unchanged)

```text
$ cd backend && uv run --extra dev pytest -q tests/test_openapi_snapshot.py --basetemp=E:/polymarket-worktrees/loop105-catalog/.ptfix2
...                                                                      [100%]
3 passed in 7.03s
```
