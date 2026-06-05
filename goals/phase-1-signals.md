---
id: phase-1-signals
phase: 1
status: DONE
depends_on: [phase-0]
workflow: backend-feature
full_spec: docs/project/QUANT_ROADMAP.md  (§3 Phase 1)
---

# Phase 1 — Signals v1: arbitrage + dutching

**Objective:** the first *real* signal in the app. Deterministic math over real Polymarket/Kalshi prices. NO prediction model, NO execution.

**Why this is next:** Phase 0 (connectors + snapshot store + CLV backtester) is shipped. `backend/app/signals/` does not exist yet.

## Scope / files
- `backend/app/signals/matching.py` — match the same event across Polymarket↔Kalshi on **resolution semantics** (normalized entities + close/resolution timestamp + resolution-source compatibility), not titles. Return a confidence; below threshold ⇒ `unconfirmed`.
- `backend/app/signals/arbitrage.py` — `price_YES(A) + price_NO(B) < 1.00` **after fees** (Kalshi fee schedule + Polymarket gas). Return gross/net spread, % return, confidence, resolution-terms warning. Exclude `unconfirmed` pairs from the headline.
- `backend/app/signals/dutching.py` — `Σ price_i < 1.00` after fees; equal-payout share counts; validate outcomes exhaustive + mutually exclusive, else flag "coverage not guaranteed."
- `backend/app/services/signals_service.py` + endpoints in `backend/app/api/v1/routes.py`: `GET /api/v1/signals/arbitrage`, `GET /api/v1/signals/dutching`.
- `backend/app/db/models.py` `signal_events` (+ Alembic migration) — persist every flagged signal for Phase 6 tracking.

## Acceptance gate
- pytest proves: arb fee math + the `<1.00` boundary; resolution-matching **positive and negative** fixtures; dutching math + exhaustiveness validation + stake equalization; `unconfirmed`-pair exclusion from the headline.
- `cd backend && uv run --extra dev pytest -q` and `ruff check app tests` green.

## Safety
No execution/order/wallet code. No "guaranteed profit" copy except where math is locked AND resolution-confirmed — and even then label fee/slippage/liquidity risk.

## PR line
`Phase 1 signals | gate=met | verify=pytest 155 passed, ruff clean | safety=paper-only,no-exec,no-keys: ok | review=manual | AutoLab=n/a | commit=5c2110b`

> Full paste-ready block: `docs/project/QUANT_ROADMAP.md` → §3 Phase 1.
