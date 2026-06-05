---
id: phase-6-overlay-tracking
phase: 6
status: QUEUED
depends_on: [phase-1, phase-2, phase-3, phase-4]
workflow: ui-feature
full_spec: docs/project/QUANT_ROADMAP.md  (§3 Phase 6)
---

# Phase 6 — Serving + overlay + honest tracking

**Objective:** surface signals + predictions in the extension overlay and a CLV track-record dashboard. Honest labels everywhere. NO execution.

## Scope / files
- `extension/src/` — overlay panels for Arbitrage, Dutching, Smart-money, Forecast. Call Phase 1–3 endpoints via `extension/src/backend-client.ts` using existing URL parsers. Each panel: the math, net-of-fees numbers, confidence, suggested (paper) stake, persistent "Research / not financial advice — verify resolution terms" label. FanDuel manual-only.
- `frontend/src/app/` — Signals + CLV dashboard. Forecast numbers show sample size, provisional flags, live CLV track record; models failing the CLV gate are clearly NOT shown as edge.
- `backend/app/services/forecast_dashboard_service.py` — reconcile persisted `signal_events` after resolution; track HONEST metrics (real vs broken arbs, realized vs theoretical spread, model CLV over time). Paper P&L uses real prices + simulated stakes.

## Acceptance gate
- Extension panels render from endpoints + handle empty states; manifest minimal-permissions + no-scraping + no-key safety tests pass.
- Dashboard shows provisional labels + live CLV track record + paper P&L from real prices.
- Reconciliation math tested.
- Verify: `cd extension && npm test && npm run typecheck && npm run build`; `cd frontend && npm run lint && npm run typecheck && npm run build`; `cd backend && uv run --extra dev pytest -q`.

## Safety
Honest labels mandatory; no execution; minimal host permissions; FanDuel manual-only.

## PR line
`Phase 6 overlay+tracking | gate=met | verify=ext+fe+be green (counts) | safety=labels,perms,manual-fanduel: ok | review=<skill/manual> | AutoLab=n/a`

> Full paste-ready block: `docs/project/QUANT_ROADMAP.md` → §3 Phase 6.
