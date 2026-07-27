# STATE115 — featured curation: flagship four

**Role:** Implementation engineer, worktree `loop115-featured`
**Commit:** `feat(loop115): featured curation — flagship four`

## Change

`backend/app/services/scanner_seed_service.py` — `is_featured` set explicitly
on EVERY `STARTER_SCANNERS` entry (was defaulted via `entry.get(..., True)`):

| is_featured | Starters |
|---|---|
| True | Big Mover Radar, Whale Flow Watch, Model Edge Radar, Triple Confirmation |
| False | High-Volume Momentum, News Pulse Confirmed, NBA Sharp Money, Election Edge Watch, Cross-Venue Divergence, Closing Soon, High Volume |

Nothing else changed in the service (seed function untouched).

`backend/tests/test_loop107_scanner_seeds.py` — added
`test_featured_curation_is_flagship_four`: seeds into the test DB, asserts
exactly the flagship four have `is_featured` True and the other six False.

## Guardrails

PAPER_TRADING_ONLY untouched. No order-path / LLM. No secrets printed.
No push/deploy. Explicit `git add` only (no `git add -A`).

## AutoLab

AutoLab: not applicable (no iterative measure) — one-shot curation flag + test.

## VERIFY (verbatim)

```text
cd backend && uv run --extra dev pytest -q tests/test_loop107_scanner_seeds.py --basetemp=E:/polymarket-worktrees/loop115-featured/.pt ; uv run --extra dev ruff check app tests
```

```text
.....                                                                    [100%]
5 passed in 33.34s
All checks passed!
```
