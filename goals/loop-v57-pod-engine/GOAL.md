# Loop V57 — Multi-pod paper strategy engine (backend)

Reference repos (READ ONLY, at E:/polymarket-reference/): TradingAgents,
freqtrade, nautilus_trader, Polymarket/agents. Extract techniques; never vendor
code wholesale; respect licenses (cite repo in module docstring when a design
is adapted).

## Outcome
AlphaEdge runs N independent paper-trading "pods" — isolated strategies with
their own config, scoring, ledger, and P&L — 24/7 in-process, all order flow
through RiskService -> OrderIntent -> OrderBookService (PAPER_TRADING_ONLY).
Simulated funds treated like real money: fees/slippage modeled, no fabricated
fills.

## Hard constraints
- NO live execution, NO exchange keys, NO withdrawal/payment code. Hyperliquid
  /Binance are DATA sources only (public endpoints) if used at all.
- Pods never bypass the order path; leakage gate applies (no post-close data
  in any signal).
- In-process loop wiring per _ALL_LOOPS/_paced_sleep/record_heartbeat pattern
  (prod has no ARQ worker).
- Migration ids <=32 chars; next free is 049+ on head 048_lock_provenance.

## Tickets (one commit each, feat(loop57): <ticket>)
- P1 Pod framework: `app/pods/` — Pod base class (config, universe,
  score_market(), decide(), size()), PodRegistry, per-pod ledger tables
  (migration 049_pods: pods, pod_trades, pod_equity_snapshots), flag
  PODS_ENABLED default false.
- P2 Scoring engine: multi-factor score (liquidity, trend strength, RSI-style
  pressure, move persistence, bounce quality) computed from OUR stored price
  history; threshold-gated entries (default >=70/100); every score component
  logged to pod_trades for the evolutionary loop.
- P3 Three concrete pods, config-driven: (a) crypto 5m momentum-fade pod on
  external BTC/ETH markets; (b) longshot-fade pod (deep-favorite maker style
  per E06 economics — honest fee model); (c) sports value pod (FIFA/MLS
  markets vs model probability edge). Each isolated, own bankroll slice,
  max-exposure caps.
- P4 In-process pod_runner loop (60s cadence, flag-gated) + heartbeat detail
  (scanned/scored/entered/exited counts) + /api/v1/pods status endpoint
  (public read: pod list, equity curve, last decisions).
- P5 Tests (pods isolated, order-path only, caps enforced, score determinism
  on fixtures, no post-close leakage) + full gate from backend/
  (ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q, CHECK COUNTS;
  ruff clean). STATE.md with counts.

Stop when P1-P5 DONE or BLOCKED in goals/loop-v57-pod-engine/STATE.md.
Never push/merge.
