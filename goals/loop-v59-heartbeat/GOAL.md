# Loop V59 — Heartbeat position manager + decision log

Reference (READ ONLY, E:/polymarket-reference/): hermes-agent, aeon (heartbeat
/self-heal patterns), freqtrade (position management). Extract techniques,
cite adapted designs, never vendor wholesale.

## Outcome
A cheap, fast, code-only heartbeat (no LLM calls in the loop) that watches
every open paper position (pods + user paper trades) on a 30-120s cadence,
evaluates exit/tighten/hold rules, records an auditable decision log, and
performs emergency exits via the normal order path. The "sub-agent heartbeat"
from the reference videos, done as deterministic code.

## Hard constraints
- Order flow ONLY via RiskService -> OrderIntent -> OrderBookService.
- Deterministic rules; no fabricated numbers; every decision row stores the
  inputs it saw. Flag HEARTBEAT_MANAGER_ENABLED default false.
- In-process loop pattern; migration 051+ (<=32 chars; V57=049, V58=050).
- Coordinate files: do NOT touch app/pods/** internals (V57's charter) — you
  may READ its tables/registry interfaces; define your own module
  app/services/heartbeat_manager.py + tables.

## Tickets (one commit each, feat(loop59): <ticket>)
- H1 Decision engine: hold/tighten/exit/emergency rules from config (time
  stop, adverse-move stop, profit-target, staleness kill); pure function,
  fixture-tested.
- H2 heartbeat_manager loop (45s default) + decision_log table (migration
  051_heartbeat: position ref, rule fired, inputs snapshot, action taken,
  latency_ms) + heartbeat detail counts in system loops status.
- H3 Emergency paths: price-feed staleness halt, daily-loss halt per pod
  (reads pod ledger read-only), global kill flag — all logged, all reversible.
- H4 `GET /api/v1/heartbeat/decisions` (recent decision log, public read) +
  ops runbook section in docs/operations.md.
- H5 Tests (each rule, halts, no order-path bypass, loop registration) + full
  gate from backend/ (CHECK COUNTS; ruff). STATE.md with counts.

Stop when H1-H5 DONE or BLOCKED in goals/loop-v59-heartbeat/STATE.md.
Never push/merge.
