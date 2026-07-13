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

## Tickets

### Workstream A — Trading engine
| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| A1 | CLOB idempotency (M-RACE-01) | TODO | |
| A2 | Atomic settlement credit (M-REL-02) | TODO | |
| A3 | Order cancellation endpoint | TODO | |
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
