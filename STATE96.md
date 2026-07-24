# Loop V96 — Multi-Factor Alpha Model

## Graph and ownership

`factors.py` contains seven deterministic, pure factor nodes. Their real edge is
a normalized score plus lock-time provenance. `validator.py` is the independent
maker-checker node; it consumes historical factor observations only after the
fan-in barrier. `alpha_service.py` reduces the current factor vector and
validator outcomes into read-only research output. `api/v1/alpha.py` exposes
that output but is intentionally not registered in `main.py`; the merge
orchestrator owns that integration.

Rejected factors are never reclassified as edge: response state contains each
rejection and its machine-readable reason. This Phase 1 implementation is
read-only over existing resolved data, so it adds no migration and does not
persist mutable runtime state.

## A1 — factor library

Status: DONE

```text
$ git log -1 --oneline
c966dec feat(loop96): A1 — add pure alpha factor library

$ cd backend && uv run --extra dev pytest -q tests/test_alpha_factors.py --basetemp=E:/polymarket-worktrees/loop96-alpha/.pt
..                                                                       [100%]
2 passed in 46.60s

$ cd backend && uv run --extra dev ruff check app tests
All checks passed!
```
