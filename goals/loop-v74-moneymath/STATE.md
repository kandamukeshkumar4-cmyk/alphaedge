# Loop V74 - Money-math review fixes - STATE

Worktree: `E:/polymarket-worktrees/loop74-money` · branch `loop74/moneymath`
Authorization: `DIR-V74-001` — advisor waived; defects were verifier-confirmed.
Scope: REPORT.md findings #7, #2, #1, #6, #10, and #9 only. Never push or merge.

## Ticket status

| Ticket | Status | Evidence |
|---|---|---|
| V74-1 Weighted CLOB average cost | DONE | `fix(loop74): weight CLOB position average cost`; 1853 passed, 28 skipped; ruff PASS |
| V74-2 Public WS notification privacy | DONE | `fix(loop74): keep notifications off public feed`; 1852 passed, 28 skipped; ruff PASS |
| V74-3 CLOB fill remaining cap | DONE | `fix(loop74): cap CLOB fills to remaining liquidity`; 1853 passed, 28 skipped; ruff PASS |
| V74-4 Paper open-lot basis and VOID credit | PENDING | |
| V74-5 CLOB VOID short debit | DONE | `fix(loop74): debit CLOB shorts on void`; 1853 passed, 28 skipped; ruff PASS |
| V74-6 Atomic paper settlement credit | PENDING | |

## LOOP LOG

| loop | date | result | proof |
|---|---|---|---|
| V74 | 2026-07-17 | STARTED | REVIEW report reconciled; six scoped fixes authorized |
| V74-1 | 2026-07-17 | DONE | weighted YES/NO long basis, partial-sell preservation, and zero-cross reset regression; backend 1853 passed, 28 skipped; ruff PASS |
| V74-2 | 2026-07-17 | DONE | public feed excludes notification PII; REST API regression retained; backend 1852 passed, 28 skipped; ruff PASS |
| V74-3 | 2026-07-17 | DONE | database-locked paired orders cap stale fill before fill, position, or ledger mutation; backend 1853 passed, 28 skipped; ruff PASS |
| V74-5 | 2026-07-17 | DONE | VOID returns both long and short accounts to their pre-trade balance; backend 1853 passed, 28 skipped; ruff PASS |
