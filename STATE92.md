# STATE92 — Portfolio Analytics (BACKEND)

## Status
**P1–P3 DONE** (2026-07-24)

Branch: `loop92/portfolio-analytics` (no push/deploy).

## Assumptions
- Closed P&L via `analytics_attribution.attributed_trades` (no E12 double-count).
- Live unrealized via portfolio `_enrich_live_pnl` / odds snapshots.
- Calibration: entry `PaperOrder.price` as implied P(outcome); deciles via `ml.calibration.reliability_curve`.
- No migration (read-only). Alembic head: `062_notif_engagement`.

## LOOP LOG
| ticket | date | result | proof |
|--------|------|--------|-------|
| P1 | 2026-07-24 | DONE | feat(loop92): P1 — portfolio analytics service |
| P2 | 2026-07-24 | DONE | feat(loop92): P2 — portfolio analytics calibration buckets |
| P3 | 2026-07-24 | DONE | feat(loop92): P3 — GET /portfolio/analytics endpoint |

## P3 proof (pre-full-suite)
```
uv run --extra dev pytest -q tests/test_portfolio_analytics.py --basetemp=.../.pt
9 passed in 11.01s
ruff: All checks passed!
```

## Deliverables
- `backend/app/services/portfolio_analytics_service.py` — `compute_portfolio_analytics`
- `GET /api/v1/portfolio/analytics?days=` (auth, 400 if days∉[1,365])
- `backend/tests/test_portfolio_analytics.py`

## Guardrails
- Paper only; no order-path changes; no new deps; no migration.

## AutoLab
AutoLab: not applicable (no iterative measure — contract feature)

## Unrelated findings (not fixed)
- None.
