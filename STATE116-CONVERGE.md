# STATE116-CONVERGE — cross-scanner convergence (audit gap #4)

Worktree: `E:/polymarket-worktrees/loop116-converge` (branch `loop116-converge/node`)
Spec: `brief.txt` (worktree root). PAPER_TRADING_ONLY. Research-only: no order-path
imports, no LLM calls, no secrets, no push/deploy.

## Status: COMPLETE

The Gemini checkpoint commit `90e0f44 wip(loop116): gemini convergence checkpoint`
was interrupted mid-edit. All 4 spec tests failed and the frontend did not compile.
This node diagnosed and finished it.

## Root cause of the 4 test failures (all one bug)

`app.include_router(scanner_convergence_router)` was placed at the END of the
include block in `backend/app/main.py`, i.e. AFTER `app.include_router(scanners_router)`.

`scanners.py` mounts `prefix="/api/v1/scanners"` and declares
`GET /{scanner_id}` with a `UUID` path parameter. FastAPI matches routes in
registration order, so every request to `/api/v1/scanners/convergence` was
captured by `/api/v1/scanners/{scanner_id}` and rejected as a bad UUID:

```
E       assert 422 == 200
E        +  where 422 = <Response [422 Unprocessable Entity]>.status_code
```

All four tests failed on the same 422 — the convergence handler never ran.
(`scanners.py` itself already orders its literal routes `/trending` and
`/featured` before `/{scanner_id}` for the same reason; a router included after
it cannot inherit that ordering.)

## Changes made

Backend
- `backend/app/main.py` — moved the ONE new include line from the end of the
  block to immediately BEFORE `app.include_router(scanners_router)`, so the
  literal `/scanners/convergence` route is registered first. Still exactly one
  added line (the brief's "one line at the end" is not satisfiable given the
  `{scanner_id}` catch-all; position is load-bearing).
- `backend/app/api/v1/scanner_convergence.py` — latest-run selection now accepts
  `status in ("completed", "empty")` and excludes `is_test` runs.
  `scanner_executor_service` finishes a successful run as `"completed"` (had
  candidates) or `"empty"` (had none); filtering on `"completed"` alone let a
  scanner whose newest run found nothing keep resurrecting stale matches from an
  older run, which breaks the spec's latest-run-only semantics. Test-mode runs
  never write the alert feed, so they must not feed convergence either.

Tests
- `backend/tests/test_loop116_converge.py` — added an autouse teardown fixture
  that pops the `get_db` dependency override. The checkpoint set the override
  globally and never removed it, leaking a closed session into sibling test
  modules. No assertion was weakened; the four spec assertions
  (two-scanner counting, single-scanner exclusion, mine-requires-auth,
  latest-run-only) are unchanged.
- `backend/tests/fixtures/openapi_snapshot.json` — regenerated via
  `scripts/regen_openapi_snapshot.py`. Exactly one path added.
- `backend/tests/test_loop26_authz_matrix.py` — authz matrix entries + counts.

Frontend
- `frontend/src/components/scanners/ScannersShell.tsx` — repaired truncated JSX.
  The interrupted edit deleted the opening of the `list` branch (`<>`,
  `<ScannerComposer/>`, the `mt-8` wrapper, the `mb-3` header row, the
  `Your scanners` heading and the `{scanners !== null ? (` guard), leaving 9
  TS1005/TS17002 parse errors. Restored from `HEAD~1` and re-wrapped under the tab.
- `frontend/src/components/scanners/ConvergencePanel.tsx` — fixed the import
  (`@/lib/api` does not exist -> `API_BASE` / `apiUrl` / `ensureApiBase` from
  `@/lib/alphaedge-api`, matching every other client), added the spec's
  `/markets/[slug]` link, the spec's exact empty-state copy
  ("No market appears in multiple scanners right now."), and rendered the
  contributing scanner names as chips per spec.

## AuthZ matrix deltas (orchestrator: resolve collisions)

The checkpoint author added NO authz entries. Added by this node:

| item | before | after |
| --- | --- | --- |
| snapshot paths | 209 | **210** |
| `_OPS` | 230 | **231** |
| `optional_user` | 3 | **4** |
| `admin` / `user` / `admin_metrics` / `public` | 41 / 70 / 1 / 115 | unchanged |

New entry: `("get", "/api/v1/scanners/convergence"): "optional_user"`
(the route depends on `get_optional_user`; anonymous is allowed for
`scope=public` and 401s for `scope=mine`).

## Migrations

Zero. `alembic heads` unchanged at `069_ident_text`. No files under
`backend/alembic/versions/` were touched.

## Verbatim STOP output

```
$ cd backend && uv run --extra dev pytest -q tests/test_loop116_converge.py --basetemp=E:/polymarket-worktrees/loop116-converge/.ptf
....                                                                     [100%]
4 passed in 7.23s
```

```
$ cd backend && uv run --extra dev ruff check app tests
All checks passed!
```

```
$ cd backend && uv run --extra dev pytest -q tests/test_loop26_authz_matrix.py tests/test_openapi_snapshot.py --basetemp=E:/polymarket-worktrees/loop116-converge/.ptf
.....                                                                    [100%]
5 passed in 29.45s
```

```
$ cd backend && uv run alembic heads
069_ident_text (head)
```

```
$ cd frontend && npm run typecheck

> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit

```

```
$ cd frontend && npm run lint

> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0

```

Regression sweep (`pytest -q -k "scanner or openapi or authz or route"`):

```
1 failed, 139 passed, 1 skipped, 2097 deselected in 61.74s (0:01:01)
FAILED tests/test_loop109_scanner_dsl.py::test_existing_seeded_scanners_still_compile
```

## Pre-existing failure — NOT this node, NOT in charter

`tests/test_loop109_scanner_dsl.py::test_existing_seeded_scanners_still_compile`
asserts `entry.get("is_featured", True) is True` for every loop107 seed. Loop115
(`6f3a203 feat(loop115): featured curation — flagship four`) made featuring
selective, so "Election Edge Watch" is now `is_featured: False`. The failure is
inherited from the parent commit; nothing in loop116 touches
`scanner_seed_service.py` or `test_loop109_scanner_dsl.py`. Left for the loop115
owner / orchestrator.

## Deviation to note

`frontend/src/lib/scanners-api.ts` documents a convention that "all fetch wiring
lives in this one file — UI components never call fetch themselves."
`ConvergencePanel.tsx` fetches directly, as the checkpoint author wrote it. The
charter forbids adding files outside the listed set, so this was left as-is
rather than extracting a `convergence-api.ts`. Flagging for a follow-up loop.

## Charter compliance

Touched only: the new router file, ONE `main.py` include line, the test file,
the authz matrix + regenerated openapi snapshot (explicitly required by the
brief), `ConvergencePanel.tsx`, `ScannersShell.tsx` tab wiring, and this STATE
file. `scanners.py`, the executor, and all artifacts/compile paths are untouched.
No `git add -A`; named files only. No push, no deploy, no secrets.
