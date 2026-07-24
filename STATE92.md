# STATE92 — Portfolio Analytics (BACKEND)

## Status
P1 DONE | P2 PENDING | P3 PENDING

## Assumptions
- Closed P&L via `analytics_attribution.attributed_trades` (no E12 double-count).
- Live unrealized via portfolio `_enrich_live_pnl` / odds snapshots.
- No migration (read-only over paper_orders).
- Alembic head unchanged: `062_notif_engagement`.

## LOOP LOG
| ticket | date | result | proof |
|--------|------|--------|-------|
| P1 | 2026-07-24 | DONE | see below |

## P1 proof
```
git log -1
```

```
uv run --extra dev pytest -q tests/test_portfolio_analytics.py --basetemp=.../.pt
3 passed in 100.69s
uv run --extra dev ruff check app/services/portfolio_analytics_service.py tests/test_portfolio_analytics.py
All checks passed!
```

AutoLab: not applicable (no iterative measure — contract feature)
