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
| scheduled-autolab   | feat/scheduled-autolab    | pending | pytest 2/2 |

## Calibration Metrics

| Date | Slug | Brier Score | Gate |
|------|------|-------------|------|
| 2026-06-09 | baseline | — | 2026-07-07 pass |

## Next Queue

- [x] Drop FIFA CSVs into `backend/app/data/fifa/` → 7 skipped tests become active
      — DONE: `intl_results.csv`, `wc2026_fixtures.csv`, `wc2026_bracket.csv`,
      `wc2026_model.pkl` present in `backend/app/data/fifa/` (see build-loop-opus48
      O10; unblocks the WC2026 loaders/model path).
- [x] GROUP BY slug/side (not id) in portfolio.py for net positions
      — DONE: `_load_paper_orders` in `backend/app/api/v1/portfolio.py:130` does
      `GROUP BY po.slug, po.side, po.outcome`; regression-locked (build-loop-opus48 O02).
- [x] Schedule calibration AutoLab loop

## AutoLab Baseline

```
AutoLab: baseline=Brier threshold=0.25 | benchmark=tests/test_calibration.py | schedule=nightly 3am UTC (.github/workflows/calibration-autolab.yml) | budget=5 | outcome=automation-armed
```
