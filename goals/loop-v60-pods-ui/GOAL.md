# Loop V60 — Pods command center UI (frontend)

## Outcome
A /pods page: the fleet dashboard for the paper-trading pods — pod cards with
equity curves, live decision-log terminal, heartbeat status, and the master
context panel per market. Bloomberg-terminal aesthetic within our existing
design system (follow frontend/.claude/CLAUDE.md and existing tokens; dark
mode first; no new UI libraries).

## Backend contracts (being built in parallel — code against these shapes,
mock in tests; graceful empty-states until they ship):
- GET /api/v1/pods -> {pods:[{id,name,status,bankroll,equity,pnl_24h,
  trades_count,last_decision_at}], equity_curves:{pod_id:[{t,equity}]}}
- GET /api/v1/heartbeat/decisions -> {decisions:[{t,pod,market,rule,action,
  latency_ms}]}
- GET /api/v1/markets/{slug}/context -> {whale_pressure,venue_gap,
  news_signal,price_trend,volume_pct,captured_at}
If a live endpoint 404s, render an honest "not yet deployed" state — never
fake data.

## Tickets (one commit each, feat(loop60): <ticket>)
- U1 Types + API clients for the three contracts (msw-style mocks like
  existing lib tests).
- U2 /pods page: pod cards grid + equity sparkline (lightweight-charts,
  existing pattern), status chips (running/halted/flag-off), honest
  paper-trading banner ("simulated funds — no execution").
- U3 Decision-log terminal component: streaming-style list, rule badge,
  action color (existing green/red trade tokens), 5s poll, blink on new row.
- U4 Market context panel embedded on market detail page (whale pressure
  gauge, venue gap, news sentiment) — descriptive only, no advice language.
- U5 Frontend gate: npm run typecheck, lint, vitest run, build — all green,
  counts in STATE.md.

NEVER: touch order/trade mutation components, fabricate numbers, promise
returns in copy, push, merge. Stop when U1-U5 DONE or BLOCKED in
goals/loop-v60-pods-ui/STATE.md.
