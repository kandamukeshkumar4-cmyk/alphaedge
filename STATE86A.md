# STATE86A — Backend node F-A (graph V86)

| Ticket | Status | Proof |
|--------|--------|-------|
| F1 | DONE | vitest: `Test Files 1 passed (1) / Tests 6 passed (6)` (`markets-fetch-cache.test.ts`) |
| F2 | DONE | `uv run --extra dev pytest -q tests/test_scanner_reliability.py --basetemp=.../.pt` → `3 passed in 30.97s` |
| F3 | DONE | `uv run --extra dev pytest -q tests/test_scanner_versions.py --basetemp=.../.pt` → `1 passed in 8.87s` |
| F4 | DONE | `uv run --extra dev pytest -q tests/test_scanner_deadletter.py --basetemp=.../.pt` → `2 passed in 8.22s` |

Full suite: `1940 passed, 28 skipped in 348.81s` (`--basetemp=.../.ptf`)
Ruff: All checks passed on F2–F4 touched paths.

AutoLab: not applicable (no iterative measure)
