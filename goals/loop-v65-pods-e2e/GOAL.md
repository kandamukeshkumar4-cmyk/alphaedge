# Loop V65 — Pods surface Playwright e2e (TESTS ONLY)

## Outcome
Playwright e2e coverage for the Loop V60 pods command center: `/pods` fleet
cards, decision-log terminal, and market context panel — all driven by mocked
API fixtures matching the live contracts (never fabricate UI numbers outside
those mocks).

## Charter (exclusive)
- YOURS: `frontend/e2e/**`, `goals/loop-v65-pods-e2e/**`
- FOREIGN: never edit `frontend/src/**`, `backend/**`, deploy configs, other
  goals. Never push/merge.

## Tickets (one commit each, `test(loop65): <ticket>`)
- T1 `/pods` page: pod cards from mocked `GET /api/v1/pods`, honest
  paper-trading banner, empty state when no pods.
- T2 Decision-log terminal: rows from mocked `GET /api/v1/heartbeat/decisions`,
  action colors (buy/sell tokens), empty state.
- T3 Market context panel on market detail: whale gauge + venue gap + absent
  states from mocked `GET /api/v1/markets/{slug}/context`.
- T4 Run ONLY the new specs once
  (`npx playwright test <files> --reporter=line`), record counts in STATE.md,
  commit. Then STOP. Max one retry if webserver fails to boot.

## Guardrails
PAPER_TRADING_ONLY; local stack only; follow existing e2e mock patterns
(`page.route` + `fulfill` like `locked-forecast.spec.ts`); never modify app
source.
