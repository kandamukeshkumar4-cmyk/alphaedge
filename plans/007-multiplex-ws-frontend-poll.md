# Plan 007: Multiplex price WebSocket + reduce catalog poll

> **Executor instructions**: Follow step by step. Run verification after each step.
> Update `plans/README.md` when done.
>
> **Drift check**: `git diff --stat 24fa35f..HEAD -- backend/app/api/v1/ws.py frontend/src/context/live-prices.tsx frontend/src/components/MultiLineChart.tsx`

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/005 (DONE)
- **Category**: perf
- **Planned at**: commit `24fa35f`, 2026-06-12

## Why this matters

Home page opens up to **24 WebSocket connections** (`collectPrioritySlugs`) plus `LivePricesProvider` polls **full** `GET /markets` every **1 second**. `MultiLineChart` adds more WS + 2s poll per hero outcome. This does not scale with tabs or market count and loads the API unnecessarily.

## Current state

- `backend/app/api/v1/ws.py`: one slug per socket (`market` query param)
- `backend/app/core/broadcast.py`: in-memory hub, max 32 queues per slug
- `frontend/src/context/live-prices.tsx`: `POLL_MS = 1000`, `LiveWsBridge` per priority slug
- `frontend/src/components/MultiLineChart.tsx` L228–247: separate WS per outcome slug
- Azure deploy: `max-replicas=1` (`scripts/deploy_azure_live.ps1` L209) — hub is single-instance OK today

## Scope

**In scope**
- `backend/app/api/v1/ws.py` — add optional `markets=a,b,c` (comma-separated, max 32)
- `backend/app/core/broadcast.py` — helper to subscribe multiple slugs
- `frontend/src/context/live-prices.tsx` — single multiplex WS, remove 1s full-catalog poll (keep 5–10s lightweight poll as fallback)
- `frontend/src/components/MultiLineChart.tsx` — consume shared context instead of own WS
- `backend/tests/test_broadcast.py` or new `test_ws_multiplex.py`
- `frontend` smoke test if exists for live prices

**Out of scope**
- Redis-backed hub / multi-replica
- `hf_stage/`

## Steps

### Step 1: Backend multiplex endpoint

Extend `/api/v1/ws/prices`:
- Accept `markets` query (comma-separated slugs) OR legacy single `market`
- Validate each slug exists (same rules as today)
- Subscribe client to all slugs; multiplex publishes with `slug` in payload
- Send initial snapshot per slug on connect

**Verify**: `pytest -q tests/test_ws_multiplex.py` (create) → pass

### Step 2: Frontend LivePricesProvider

- Replace N `LiveWsBridge` with one connection: `markets=${prioritySlugs.join(',')}`
- Change poll interval to **5000ms**; poll only slugs missing from last WS tick OR use `fetchLatestPrice` batch if added later
- Remove duplicate WS from `MultiLineChart`; read prices from `useLivePricesMap()` / context

**Verify**: `cd frontend && npm run typecheck && npm run lint && npm run test` → pass

### Step 3: Manual smoke

- Open home with devtools Network → WS: expect **1** connection, ticks for hero slugs
- Hero chart still updates when Kalshi prices move

## STOP conditions

- Multiplex breaks existing single-market clients without backward compat
- WS message shape change breaks `NotificationBell` or market detail pages
- Requires Redis / infra change for single-replica deploy

## Done criteria

- [ ] Backward compatible single `market=` WS still works
- [ ] Home uses ≤1 WS for priority slugs
- [ ] No 1s full `fetchMarkets` poll in `LivePricesProvider`
- [ ] Backend + frontend verification commands pass
- [ ] `plans/README.md` row 007 → DONE
