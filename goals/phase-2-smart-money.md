---
id: phase-2-smart-money
phase: 2
status: DONE
depends_on: [phase-0]
workflow: backend-feature
full_spec: docs/project/QUANT_ROADMAP.md  (§3 Phase 2)
---

# Phase 2 — Smart-money / whale tracker

**Objective:** verifiable on-chain copy *signal* (not copy *execution*). Read Polygon for Polymarket; show profitable wallets' current positions on the viewed market. Real blockchain data, not screenshots.

## Scope / files
- `backend/app/data/connectors/onchain.py` (extend) — read fills/positions from the Polymarket subgraph (Goldsky) + Polygon RPC; compute realized + unrealized P&L, ROI, hit rate from on-chain data only.
- `backend/app/signals/smart_money.py` — discover historically-profitable wallets (configurable thresholds); for a market, return which tracked wallets hold a position and on which side.
- `backend/app/services/wallet_service.py` + endpoint `GET /api/v1/signals/smart-money`.
- `backend/app/db/models.py` `tracked_wallets`, `wallet_positions` (+ migration).

## Acceptance gate
- P&L/ROI computed from a recorded on-chain **fixture** wallet matches expected values.
- Market-position lookup returns the wallet's current side.
- Safety test asserts **no private-key field and no signing code** exists anywhere.
- `cd backend && uv run --extra dev pytest -q` + ruff green.

## Safety
Read-only. No copy-trading execution. On-chain reads only; no account credentials.

## PR line
`Phase 2 smart-money | gate=met | verify=pytest 159 passed, ruff clean | safety=read-only,no-keys: ok | review=manual | AutoLab=n/a`

> Full paste-ready block: `docs/project/QUANT_ROADMAP.md` → §3 Phase 2.
