# STATE105 — markets catalog pagination (backend)

**Branch:** `loop105-catalog/node`  
**Seat:** Cursor Grok 4.5 High (BACKEND)  
**Date:** 2026-07-24  
**Status:** DONE (proof below)

## Bug confirmed

`backend/app/api/v1/routes.py` `list_markets` had no `limit`/`offset` params. FastAPI discarded
`?limit=` / `?offset=` query args; every call returned the full catalog.

## Implemented (exact contract)

1. `list_markets`: `limit: int = 100`, `offset: int = 0`; validate `1..500` / `offset >= 0` → 400.
2. Response shape unchanged: `list[MarketResponse]`.
3. Headers on every 200: `X-Total-Count`, `X-Page-Limit`, `X-Page-Offset`.
4. `MarketService.list_public_markets(*, …, limit=100, offset=0) -> tuple[list, int]` with SQL
   `LIMIT`/`OFFSET` + count-before-slice (not Python slice-after-fetch).
5. Cache key `(category, sort, q, limit, offset)` stores `(rows, total)`.

## Forced call-site unpacks (signature return type)

Not in the exclusive charter list, but required so the new `tuple[list, int]` return does not
break internal consumers (one-line each):

- `backend/app/api/v1/home.py`
- `backend/app/api/v1/categories.py`
- `backend/app/api/v1/opportunities.py`

## Authz matrix

`("get", "/api/v1/markets")` still public. Path set unchanged → **no edit** to
`test_loop26_authz_matrix.py`. OpenAPI surface snapshot regen wrote identical path/method map
(query params are not part of that fixture).

## Unrelated findings (not fixed)

- Prod catalog still huge; callers that need the full set must page (`offset` walk) or raise
  `limit` (max 500). Frontend node owns consumer updates.
- `home`/`opportunities` still take the first page (default 100) then slice in Python — fine for
  their current top-N use, but they no longer see markets beyond offset 0 without an explicit
  higher limit/page.

## NEEDS USER

(none)

## AutoLab

AutoLab: not applicable (no iterative measure) — one-shot contract fix with payload proof.

---

## STOP CONDITION PROOF (pasted)

### 1) Pagination tests

```text
$ cd backend && uv run --extra dev pytest -q tests/test_loop105_markets_pagination.py --basetemp=E:/polymarket-worktrees/loop105-catalog/.pt
.........                                                                [100%]
9 passed in 99.24s (0:01:39)
```

### 2) Ruff

```text
$ cd backend && uv run --extra dev ruff check app tests
All checks passed!
```

### 3) OpenAPI snapshot regen

```text
$ cd backend && uv run python scripts/regen_openapi_snapshot.py
wrote E:\polymarket-worktrees\loop105-catalog\backend\tests\fixtures\openapi_snapshot.json (203 paths)
```

(git: no content change — surface fixture is path/method only; limit/offset are query params.)

### 4) Full suite

```text
$ cd backend && uv run --extra dev pytest -q --basetemp=E:/polymarket-worktrees/loop105-catalog/.ptf
2090 passed, 28 skipped in 627.77s (0:10:27)
```

### 5) Measured payload (local uvicorn, sqlite + 250 seeded + catalog seed → 272 total)

```text
GET /api/v1/markets           -> 44732 bytes status=200 n=100
  headers: X-Total-Count=272 X-Page-Limit=100 X-Page-Offset=0
GET /api/v1/markets?limit=10  -> 5958 bytes status=200 n=10
  headers: X-Total-Count=272 X-Page-Limit=10 X-Page-Offset=0
```

Default and `limit=10` **differ**. Default returns 100 rows, not the full 272.

ASGI cross-check (250 markets only):

```text
GET /api/v1/markets           -> 41892 bytes status=200 n=100 X-Total-Count=250
GET /api/v1/markets?limit=10  -> 4182 bytes status=200 n=10 X-Total-Count=250
```

### Prod before (reference from brief)

```text
/api/v1/markets                 -> 2353865 bytes
/api/v1/markets?limit=3         -> 2353865 bytes  (no-op pre-fix)
```

---

## git log --oneline

```text
14762be test(loop105): cover GET /markets pagination contract
a8823ea fix(loop105): unpack list_public_markets (rows, total) at internal callers
84cb6d8 perf(loop105): honor limit/offset on GET /markets with page headers
42d4592 perf(loop105): paginate list_public_markets with DB LIMIT/OFFSET
9bfa413 merge(loop102): alpha runs/signal/hypotheses UI (Qwen, Grok rubric-PASS)
```
