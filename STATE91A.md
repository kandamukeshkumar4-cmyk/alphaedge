# Loop 91 — Backend node S-A

Scope: additive market search only. Allowed files are the service, router,
focused tests, and this state file. No migrations, orders, or paper-trading
guardrail changes.

## Tickets

- S1 `feat(loop91): S1 — market search service`: implementation staged for
  focused verification and commit.
- S2 `feat(loop91): S2 — public market search router`: pending.
- S3 `feat(loop91): S3 — market search tests`: pending.

The orchestrator wires the new router in `main.py` at merge time; `main.py`
was intentionally not edited in this worktree.

## Proof log

Proof output will be appended after each ticket commit. Required commands:

```text
cd backend
uv run --extra dev pytest -q tests/test_market_search.py --basetemp=E:/polymarket-worktrees/loop91-search/.pt
uv run --extra dev ruff check app tests
uv run --extra dev pytest -q --basetemp=.ptf
```
