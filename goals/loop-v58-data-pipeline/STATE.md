# loop-v58-data-pipeline — STATE

## Status
**D1–D5 DONE** (2026-07-17)

Branch: `loop58/data-pipeline` (no push/merge).

## LOOP LOG
| ticket | date | result | proof |
|--------|------|--------|-------|
| D1 | 2026-07-17 | DONE | `feat(loop58): D1 whale flow — large-trade tape, whale_events, pressure` — migration 050_whale_flow; `app/signals/whale_flow.py`; service + in-process/ARQ loop; pressure ∈ [-1,1]; rate limit + circuit breaker |
| D2 | 2026-07-17 | DONE | `feat(loop58): D2 cross-venue gap — store gaps + top-gaps API` — migration 051_venue_gaps; venue_gap signal/service; `GET /api/v1/venue-gaps`; 60s loop |
| D3 | 2026-07-17 | DONE | `feat(loop58): D3 master context API — market context + fleet digest` — `GET /api/v1/markets/{slug}/context`, `GET /api/v1/context/digest` |
| D4 | 2026-07-17 | DONE | `feat(loop58): D4 wire whale_pressure + venue_gap into prediction graph` — `whale_signal` node; `WHALE_SIGNAL_ENABLED` default false |
| D5 | 2026-07-17 | DONE | `feat(loop58): D5 tests + gate + STATE` — mocked externals; rate-limit; leakage timestamps; context shape; full ruff + pytest |

## Gate (paste)
```
uv run --extra dev ruff check app tests
All checks passed!

ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q
1754 passed, 28 skipped in 332.16s (0:05:32)
```

## Deliverables
- **D1** `whale_events` table; large-trade poll via Polymarket data-api (`filterType=CASH`); `whale_pressure` ∈ [-1,1]
- **D2** `venue_gaps` table; PM−KS implied gap + staleness; top gaps API
- **D3** Master context JSON + fleet digest
- **D4** Graph node after nemotron; flag-gated features only
- **D5** `tests/test_loop58_data_pipeline.py` + graph test list updates

## Guardrails
- Read-only external calls; circuit breaker + min poll interval
- No order-path changes; `PAPER_TRADING_ONLY` untouched
- Leakage: all observations timestamped at capture; consumers filter pre-close
- `WHALE_SIGNAL_ENABLED` default false
- Migration ids 050+ (V57 coordinates 049); never push/merge

## Reference technique (read-only)
- polymarket-whales: large-trade threshold + poll cadence
- polyterm DataAPI: global tape `filterType=CASH` / `filterAmount`
- polyterm market_compare: probability_gap idea
- No wholesale vendoring

## AutoLab
AutoLab: not applicable (no iterative measure — pipeline wiring, not benchmark)

## Unrelated findings (not fixed)
- None blocking. Existing agent tests hard-coded GRAPH_NODES order — updated in D5 only where required by the new node.
