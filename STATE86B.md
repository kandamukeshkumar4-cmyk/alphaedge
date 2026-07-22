# STATE86B — Graph V86, node F-B (backend, loop86-testmode worktree)

Scope charter: `backend/**` + this file ONLY. Paper-trading simulation only —
no orders, no payment rails; scanners are research artifacts (RiskService →
OrderIntent → OrderBookService is untouched).

## Tickets

- **T1 — test-mode execution**: `run_scanner(db, scanner, test_mode=False)`;
  test mode caps universe at 20, flags `ScannerRun.is_test` (new column,
  migration `061_scanner_test_runs`), writes NO alert feed rows + NO email,
  and `result` gains `{"test_mode": true}`. Tests: `backend/tests/test_scanner_testmode.py` (3 cases).
- **T2 — pre-publish endpoints**: `POST /api/v1/scanners/{id}/test-run` and
  `POST /api/v1/scanners/{id}/test-email` (one email via the C7 helper when
  SMTP configured, else `{"sent": false, "reason": "smtp not configured"}` HTTP 200).
- **T3 — publish gate**: `POST /api/v1/scanners/{id}/publish` flips
  draft→active only with an `is_test=true` run (status completed/empty) for the
  current spec version, else HTTP 409 `{"detail": "run a test first"}`.

## Decisions / integration notes

1. Migration `061_scanner_test_runs` chains to local head `059_community`
   (revision id 21 chars ≤ 32). No `060_*` migration exists in this worktree;
   if a sibling node (e.g. loop86-reliability) lands `060`, integration must
   reconcile the alembic chain (rebase down_revision or add a merge revision).
2. T3's "current spec version" gate needs to know which spec version a test run
   exercised. No extra column: test-mode runs stamp
   `result["spec_version"] = scanner.version` alongside `result["test_mode"]`
   (T1's `_test_mode_result_fields`). Production runs keep the prior result shape.
3. Auth: `test-run` / `test-email` use the same visibility check as `/{id}/run`
   (owner or public); `publish` is owner-only like `pause`/`resume` (state
   transition). Test-run does NOT auto-flip draft→active (only `/run` and
   `/publish` change status).

## Proof log

### T1 — test-mode execution

Commands run from `backend/` (CLAUDE.md verification rule); test path resolves
to `backend/tests/test_scanner_testmode.py`, basetemp as chartered.

```
$ uv run --extra dev pytest -q tests/test_scanner_testmode.py --basetemp=E:/polymarket-worktrees/loop86-testmode/.pt
...                                                                      [100%]
3 passed in 34.69s

$ uv run --extra dev ruff check app tests
All checks passed!
```

### T2 — pre-publish endpoints (test-run / test-email)

```
$ uv run --extra dev pytest -q tests/test_scanner_testmode.py --basetemp=E:/polymarket-worktrees/loop86-testmode/.pt
......                                                                   [100%]
6 passed in 8.64s

# Regression: C7 email helper refactor (send_scanner_fired_email unchanged behavior)
$ uv run --extra dev pytest -q tests/test_scanner_email.py --basetemp=E:/polymarket-worktrees/loop86-testmode/.pt
..                                                                       [100%]
2 passed in 5.76s

$ uv run --extra dev ruff check app tests
All checks passed!
```

### T3 — publish gate

```
$ uv run --extra dev pytest -q tests/test_scanner_testmode.py --basetemp=E:/polymarket-worktrees/loop86-testmode/.pt
........                                                                 [100%]
8 passed in 9.11s

$ uv run --extra dev ruff check app tests
All checks passed!
```

### FULL suite (from `backend/`)

```
$ uv run --extra dev pytest -q --basetemp=.ptf
1942 passed, 28 skipped in 340.99s (0:05:40)
```

## Commits

```
954ce77 feat(loop86): T1 — test-mode execution
382662b feat(loop86): T2 — pre-publish test-run and test-email endpoints
017e011 feat(loop86): T3 — publish gate requires a pre-publish test run
```

T1–T3 DONE. Node F-B stopping (no push/deploy, per charter).
