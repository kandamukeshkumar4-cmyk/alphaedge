# STATE117-UILIE — finished green

Date: 2026-07-27
Work dir: `E:/polymarket-worktrees/loop117-uilie`
Branch: `loop117-uilie/node`

## Defect (code, not test)

`list_scanners` / `featured_scanners` used
`.distinct(ScannerRun.scanner_id)` + `ORDER BY scanner_id, started_at DESC`.
That is Postgres `DISTINCT ON` (correct newest-per-group). On SQLite
(tests) the column arg is dropped → plain `DISTINCT` returns all runs;
last-wins dict then kept the **oldest** run. Test saw run1 (12:00) instead
of run2 (13:00). Detail path (`_latest_run` LIMIT 1) was already correct.

## Fix

Replaced DISTINCT ON batch with dialect-portable `row_number()` window
(`_latest_runs_batch`): one query, rn==1 per `scanner_id`, attach via
`_scanner_out(..., latest_run=...)`. Absent runs → `latest_run` null.
`main.py` polymarket_ws in-stream heartbeat left as-is (its test green).

## Files

- `backend/app/api/v1/scanners.py` — `_latest_runs_batch` + list/featured
- `backend/app/main.py` — polymarket_ws heartbeat (pre-existing, kept)
- `backend/tests/test_loop117_uilie.py` — D6 + D7 contract tests
- `STATE117-UILIE.md` — this file

## VERIFY (verbatim)

```
$ cd backend && uv run --extra dev pytest -q tests/test_loop117_uilie.py tests/test_loop107_scanner_seeds.py --basetemp=E:/polymarket-worktrees/loop117-uilie/.pt
........                                                                 [100%]
8 passed in 18.03s
PYTEST_EXIT=0

$ uv run --extra dev ruff check app tests
All checks passed!
RUFF_EXIT=0
```

## Disposition

DONE. Commit: `fix(loop117): D6 latest_run on list/featured + ws heartbeat (finished)`.
No secrets/push/deploy. AutoLab: not applicable (no iterative measure).
