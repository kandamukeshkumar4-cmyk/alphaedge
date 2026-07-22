# STATE87B — Graph V87, node P-B (backend, loop87-selfheal worktree)

Scope charter: `backend/**` + this file ONLY. Paper-trading simulation only —
no orders, no payment rails; scanners are research artifacts (RiskService →
OrderIntent → OrderBookService is untouched). No new migrations (P-A owns them).

## Tickets

- **H1 — error classifier**: `scanner_heal_service.classify_step_error` → 8 classes.
- **H2 — bounded repairs**: deterministic repair map in step runner; `result.repairs`.
- **H3 — healing visibility**: runs list `repairs_count`; detail payload `repairs` list.

## Proof log

### H1 — error classifier

```
$ cd backend && uv run --extra dev pytest -q tests/test_scanner_heal.py --basetemp=E:/polymarket-worktrees/loop87-selfheal/.ptf
...............                                                          [100%]
15 passed in 5.26s

$ uv run --extra dev ruff check app/services/scanner_heal_service.py tests/test_scanner_heal.py
All checks passed!
```

### H2 — bounded repairs

```
$ cd backend && uv run --extra dev pytest -q tests/test_scanner_heal.py --basetemp=E:/polymarket-worktrees/loop87-selfheal/.ptf
..................                                                       [100%]
18 passed in 5.98s

$ uv run --extra dev pytest -q tests/test_scanner_executor.py tests/test_scanner_reliability.py tests/test_scanner_deadletter.py tests/test_scanner_heal.py --basetemp=E:/polymarket-worktrees/loop87-selfheal/.ptf
25 passed in 8.44s

$ uv run --extra dev ruff check app/services/scanner_heal_service.py app/services/scanner_executor_service.py tests/test_scanner_heal.py
All checks passed!
```

### H3 — healing visibility

```
$ cd backend && uv run --extra dev pytest -q tests/test_scanner_heal.py --basetemp=E:/polymarket-worktrees/loop87-selfheal/.ptf
...................                                                      [100%]
19 passed in 6.02s

$ uv run --extra dev ruff check app/schemas/scanners.py app/api/v1/scanners.py tests/test_scanner_heal.py
All checks passed!
```
