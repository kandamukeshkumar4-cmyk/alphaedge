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
| codex-first | Claude routes hands-on implementation to Codex, then reviews/verifies |
| calibration-verifier | Check Brier score, update STATE.md |
| portfolio-monitor | Check portfolio aggregation correctness |
| prediction-loop-runner | Iterative Brier improvement (AutoLab) |

## E2E ship loops

| Loop | Command / prompt | Purpose |
|------|------------------|---------|
| 0–6 | `goals/e2e-ship/STATE.md` LOOP LOG | Live-data homepage, journey, intelligence, cron verifier |
| 7 | `/loop7-ux` or `goals/e2e-ship/LOOP7.md` | Post-audit UX gaps (ATLAS, health, auth header, leaderboard, labels) |
| **8** | `/loop8-vendor` or `goals/e2e-ship/LOOP8.md` | Report-parity: toast flood, arb UI, Quest→Clones/Backtest, vendor MCP tools |

### Loop design notes (ClaudeDevs)

- Prefer **goal-based** loops: deterministic `done_when` + turn cap (40).
- **Orchestrator** freezes the spec; **executor** implements work orders; **advisor** ≤1×.
- Encode verification in skills/scripts (`verify_prod.py`, pytest, e2e) — not agent judgment.

## Merge order rule

For loops that touch market_detail.py: merge LAST.
For loops that only add new files: merge in any order.
