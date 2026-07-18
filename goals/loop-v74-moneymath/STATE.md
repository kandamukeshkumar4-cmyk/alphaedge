# Loop V74 - Money-math review fixes - STATE

Worktree: `E:/polymarket-worktrees/loop74-money` · branch `loop74/moneymath`
Authorization: `DIR-V74-001` — advisor waived; defects were verifier-confirmed.
Scope: REPORT.md findings #7, #2, #1, #6, #10, and #9 only. Never push or merge.

## Ticket status

| Ticket | Status | Evidence |
|---|---|---|
| V74-1 Weighted CLOB average cost | DONE | `fix(loop74): weight CLOB position average cost`; 1853 passed, 28 skipped; ruff PASS |
| V74-2 Public WS notification privacy | PENDING | |
| V74-3 CLOB fill remaining cap | PENDING | |
| V74-4 Paper open-lot basis and VOID credit | PENDING | |
| V74-5 CLOB VOID short debit | PENDING | |
| V74-6 Atomic paper settlement credit | PENDING | |

## LOOP LOG

| loop | date | result | proof |
|---|---|---|---|
| V74 | 2026-07-17 | STARTED | REVIEW report reconciled; six scoped fixes authorized |
| V74-1 | 2026-07-17 | DONE | weighted YES/NO long basis, partial-sell preservation, and zero-cross reset regression; backend 1853 passed, 28 skipped; ruff PASS |
