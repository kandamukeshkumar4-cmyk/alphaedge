# STATE92 — Portfolio Analytics (BACKEND)

## Status
P1 DONE | P2 DONE | P3 PENDING

## Assumptions
- Closed P&L via `analytics_attribution.attributed_trades` (no E12 double-count).
- Live unrealized via portfolio `_enrich_live_pnl` / odds snapshots.
- Calibration: entry `PaperOrder.price` as implied P(outcome); deciles via `ml.calibration.reliability_curve`.
- No migration (read-only over paper_orders). Head: `062_notif_engagement`.

## LOOP LOG
| ticket | date | result | proof |
|--------|------|--------|-------|
| P1 | 2026-07-24 | DONE | feat(loop92): P1 — portfolio analytics service |
| P2 | 2026-07-24 | DONE | see below |

## P2 proof
```
```

AutoLab: not applicable (no iterative measure — contract feature)
