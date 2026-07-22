# STATE82 — Loop V82 Scanner Studio (Wave C backend)

| Ticket | Status | Proof |
|--------|--------|-------|
| C1 | DONE | 1 passed in 34.32s |
| C2 | DONE | 3 passed in 5.73s |
| C3 | DONE | 2 passed in 5.92s |
| C4 | DONE | 1 passed in 6.80s |
| C5 | DONE | 1 passed in 26.87s |

## Full suite
`uv run --extra dev pytest -q --basetemp=.../.ptf` → **1923 passed, 28 skipped**; 1 unrelated flake (`test_backtest_cli_accepts_snapshot_feature_matrix` FileNotFound on Windows basetemp) **passed on retry**. Scanner tests 7/7 green. No ARQ scheduling (later ticket). AutoLab: not applicable (no iterative measure).
