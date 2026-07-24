# STATE101 — real-time WebSocket price push

Graph: W1 (backend) → W2 (frontend). Stop when both DONE. No push.

## LOOP LOG

| loop | date | result | proof |
|------|------|--------|-------|
| W1 | 2026-07-24 | DONE | `pytest -q tests/test_ws_prices.py` → 6 passed; `ruff check` → All checks passed |
| W2 | 2026-07-24 | DONE | `npm run typecheck` ok; `npm run lint` ok; vitest 10 passed |

## Notes

- Reuse `event_bus` `market.tick` (no new bus). Paper-only. No order path.
- `/api/v1/ws/prices?market=<slug>` filters bus ticks → `{slug, yes_price, ts}`.
- `useLivePrices` opens WS first; on error/close falls back to 15s poll; pause-on-hidden kept; `{price, source: "ws"|"poll", lastUpdated}`.
- AutoLab: not applicable (no iterative measure)

## Unrelated finding (not fixed)

- `useMarketPrice` / `useLiveMarket` still expect `{yes, no}` frames; new tick shape is `{yes_price}`. Out of charter.
