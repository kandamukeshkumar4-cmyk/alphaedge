# Loop V15 — Massive Backend Completion Loop (STATE)

Read `GOAL.md` first — it is the constitution. One ticket per iteration.
Update this file EVERY iteration before ending the session. Append-only per
workstream section; do not edit another workstream's rows.

## Worktree assignments

| Workstream | Worktree | Branch | Runner |
|---|---|---|---|
| A — Trading engine | E:/polymarket-worktrees/loop15-a | loop15/a-trading | (assign) |
| B — Portfolio/analytics | E:/polymarket-worktrees/loop15-b | loop15/b-analytics | (assign) |
| C — Connectors | E:/polymarket-worktrees/loop15-c | loop15/c-connectors | (assign) |
| D — ML lifecycle | E:/polymarket-worktrees/loop15-d | loop15/d-ml | (assign) |
| E — Platform/observability | E:/polymarket-worktrees/loop15-e | loop15/e-platform | (assign) |

Integration branch: `loop3-agent-memory` (orchestrator merges + pushes to
`origin loop3-agent-memory:codex/alphaedge-base` after idle-check + full gate).

## MIGRATION CLAIMS (serialize Alembic — claim BEFORE writing)

| Number | Claimed by | Ticket | Status |
|---|---|---|---|
| 038 | (loop-v14 may claim — check its STATE before taking) | — | — |

## SHARED FILE CLAIMS (claim BEFORE editing a shared file — see GOAL.md rule 4)

| File | Claimed by | Ticket | Status |
|---|---|---|---|
| (none) | | | |

## Tickets

### Workstream A — Trading engine
| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| A1 | CLOB idempotency (M-RACE-01) | BLOCKED-ON-USER | Started 2026-07-13T10:16:41-04:00.<br>Exists: CLOB submission is `POST /api/v1/markets/{slug}/orders` in `backend/app/api/v1/routes.py`; `OrderBookService.submit_order` persists `Order` rows, while migration 037 only protects `paper_orders`.<br>Missing: no CLOB idempotency header/field, no durable `(account_id, idempotency_key)` uniqueness, and no concurrent replay test.<br>Plan/blocker: a correct fix must edit `backend/app/api/v1/routes.py`, `backend/app/db/models.py`, and an Alembic migration, all outside Workstream A's exclusive charter. User/orchestrator must expand ownership or move A1 to an owner of those files. AutoLab: not applicable (no iterative measure). |
| A2 | Atomic settlement credit (M-REL-02) | BLOCKED-ON-USER | Started 2026-07-13T10:19:38-04:00.<br>Exists: `settle_market` calls `LedgerService.credit`; `credit` locks the account and then mutates `account.cash_balance += amount` before inserting the ledger entry.<br>Missing: the required single atomic `UPDATE accounts SET cash_balance = cash_balance + :amount RETURNING cash_balance` and a concurrent-settlement invariant test.<br>Plan/blocker: the correct change must edit `backend/app/services/settlement_service.py` and/or `backend/app/services/ledger_service.py`; neither matches Workstream A's exclusive `backend/app/services/order_*` ownership. User/orchestrator must expand ownership or reassign A2. AutoLab: not applicable (no iterative measure). |
| A3 | Order cancellation endpoint | BLOCKED-ON-USER | Started 2026-07-13T10:20:46-04:00.<br>Exists: `POST /api/v1/orders/{order_id}/cancel` and `OrderBookService.cancel_order` already cancel OPEN/PARTIAL orders; current tests prove a basic cancel releases computed reserved cash.<br>Missing: owner mismatch returns 400 rather than 403, filled/cancelled returns 400 rather than 409, cancellation lacks row locking/idempotent concurrent behavior, and no order-status event is exposed through the public WS multiplexer.<br>Plan/blocker: service locking/event emission fits `order_*`, but end-to-end completion also requires out-of-charter `backend/app/api/v1/routes.py` and `backend/app/api/v1/ws.py`. User/orchestrator must expand ownership or reassign A3. AutoLab: not applicable (no iterative measure). |
| A4 | Order expiration (GTD) sweep | TODO | |
| A5 | Order history/status API | TODO | |
| A6 | [LIVE] Order lifecycle soak | TODO | |

### Workstream B — Portfolio & social analytics
| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| B1 | Leaderboard completed | TODO | leaderboard.py exists — read first |
| B2 | Performance attribution | TODO | |
| B3 | Watchlists completed | TODO | migration 035 exists — read first |
| B4 | Trade activity feed + WS topic | TODO | |
| B5 | Equity-curve snapshots | TODO | needs migration — claim number |

### Workstream C — Connector hardening
| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| C1 | Connector resilience audit | TODO | |
| C2 | Sports results connector | TODO | signals only — NOT resolution (loop-v14) |
| C3 | Source health endpoint | TODO | |
| C4 | [LIVE] Connector soak | TODO | |

### Workstream D — ML lifecycle
| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| D1 | Model registry completed | TODO | model_registry.py/versioning.py exist — read first |
| D2 | Drift detection worker | TODO | read-only consumer of ForecastScore |
| D3 | Drift API + in-app alert | TODO | |
| D4 | Scheduled retrain (flag-gated OFF) | TODO | never auto-activates |
| D5 | AutoLab calibration pass | TODO | blocked-check: needs ≥100 resolved |

### Workstream E — Platform & observability
| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| E1 | Uniform rate limiting | TODO | |
| E2 | Prometheus /metrics | TODO | |
| E3 | In-app alert rules | TODO | read alert_dispatch first |
| E4 | OpenAPI polish + schema snapshot | TODO | |
| E5 | [LIVE] Ops soak under load | TODO | |

## LOOP LOG (append one entry per iteration)

<!-- 2026-07-13 · <workstream> · <ticket> · <result> · gate output pasted -->

2026-07-13 · A · A1 · BLOCKED-ON-USER · Scope audit only; no implementation or gate run. Required files are outside the exclusive Workstream A charter: `backend/app/api/v1/routes.py`, `backend/app/db/models.py`, and a new Alembic migration.

2026-07-13 · A · A2 · BLOCKED-ON-USER · Scope audit only; no implementation or gate run. Atomic settlement credit lives in out-of-charter `backend/app/services/settlement_service.py` and `backend/app/services/ledger_service.py`.

2026-07-13 · A · A3 · BLOCKED-ON-USER · Scope audit only; no implementation or gate run. Endpoint status semantics and WS exposure require out-of-charter `backend/app/api/v1/routes.py` and `backend/app/api/v1/ws.py`.

Workstream A REORGANIZE (2026-07-13): three consecutive iterations produced no DONE ticket because the charter's exclusive globs do not include the actual implementation surfaces named by A1-A3. Stop before A4 per the loop condition. Re-plan by granting A ownership of `api/v1/routes.py`, `api/v1/ws.py`, `db/models.py`, `services/ledger_service.py`, `services/settlement_service.py`, the necessary worker/cron files, schemas, and serialized Alembic migrations, or split/reassign the tickets to the owners of those files.

Ownership audit (2026-07-13): `loop-grok-backend` has live uncommitted edits in `backend/app/workers/tasks.py`, so A4 cannot claim that file. Registered worktree `feat/market-resolution` has unmerged commits touching `backend/app/db/models.py`, `backend/app/schemas/market.py`, `backend/app/services/settlement_service.py`, and Alembic versions, so A1/A2/A4 need an explicit owner/merge decision before those surfaces move. No current worktree diff was found for `backend/app/api/v1/routes.py`, `backend/app/api/v1/ws.py`, or `backend/app/services/ledger_service.py`, but the written charter still does not authorize A to edit them.
