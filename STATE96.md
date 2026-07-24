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

Status: IN PROGRESS
