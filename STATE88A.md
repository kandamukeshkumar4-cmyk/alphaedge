# STATE88A — K-A Kalshi WebSocket authentication

Status: BLOCKED — prerequisite dependency is not present.

## Escalation

- Node: K-A, graph V88.
- Work order: K1 signing helper, K2 Kalshi stream header wiring, K3 Railway
  readiness runbook.
- Required K1 implementation uses the `cryptography` library for RSA-PSS-
  SHA256 signatures.
- Checked first as instructed: `backend/pyproject.toml` does not declare
  `cryptography` in runtime or dev dependencies. The existing `backend/uv.lock`
  also has no `cryptography` package entry.
- The work order explicitly says to stop and escalate instead of adding the
  dependency when it is absent. Therefore no source, test, configuration,
  migration, or dependency changes were made.
- D3 diagnosis confirms the current root cause: `KalshiMarketStream` inherits
  the base bare `websockets.connect` path and sends no authentication headers.

## Decision needed

Approve a revised work order that permits adding the approved `cryptography`
dependency, or provide an already-approved project dependency that exposes the
required RSA-PSS-SHA256 signing API. The K1–K3 tickets cannot be implemented
under the current no-new-dependencies constraint.

## Verification

- K1/K2/K3: not done; no commits created for tickets.
- Per-ticket pytest and Ruff commands: not run because the hard prerequisite
  failed before implementation.
- Full suite and `orchestration/gate.py`: not run because the task is blocked.
- Pre-existing untracked files `luna-k-prompt.txt` and `luna-k.log` were
  preserved unchanged.
