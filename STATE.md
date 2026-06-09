# AlphaEdge Loop State

> Updated by calibration loop on each run. Do not edit manually.

## Loop Registry

| Loop | Branch | Merged | Gate |
|------|--------|--------|------|
| portfolio-positions | feat/portfolio-positions | pending | pytest 5/5 |
| market-resolution   | feat/market-resolution   | pending | pytest 7/7 |
| deploy-health       | feat/deploy-health       | pending | pytest 4/4 |
| market-predictions-api | feat/market-predictions-api | - | - |
| state-calibration   | feat/state-calibration   | - | - |
| agent-skills        | feat/agent-skills        | - | - |

## Calibration Metrics

| Date | Slug | Brier Score | Gate |
|------|------|-------------|------|
| 2026-06-09 | baseline | — | pending first run |

## Next Queue

- [ ] Drop FIFA CSVs into `backend/app/data/fifa/` → 7 skipped tests become active
- [ ] GROUP BY slug/side (not id) in portfolio.py for net positions
- [ ] Schedule calibration AutoLab loop

## AutoLab Baseline

```
AutoLab: baseline=Brier threshold=0.25 | benchmark=tests/test_calibration.py | iterations=0 | budget=5 | outcome=pending first run
```
