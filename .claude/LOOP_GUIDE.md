# AlphaEdge Loop Guide

## How to start a new loop

1. Check STATE.md for what's pending
2. Branch from codex/alphaedge-base (after last merge)
3. Use the agent skill file for the loop type
4. Always pair a maker agent with calibration-verifier as checker
5. Run acceptance gate before PR

## Active skills

| Skill | Purpose |
|-------|---------|
| calibration-verifier | Check Brier score, update STATE.md |
| portfolio-monitor | Check portfolio aggregation correctness |
| prediction-loop-runner | Iterative Brier improvement (AutoLab) |

## Merge order rule

For loops that touch market_detail.py: merge LAST.
For loops that only add new files: merge in any order.
