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

## Token-budget law (binding, 2026-07-17)

Token budget is the TOP orchestration priority. Every loop, review, or runner
prompt MUST contain, in this order of importance:

1. **Exit condition** — "stop when <tickets> DONE or BLOCKED in STATE.md" /
   "report, end, wait for confirmation". No prompt ships without one.
2. **Caps** — findings capped (e.g. max 5, zero is fine), review rounds
   capped (one round, max 3 parallel reviewers, one synthesis; never start
   another round without an explicit new order).
3. **One statement per instruction** — no "deep/profound/comprehensive"
   adjectives; they buy tokens, not quality.
4. **Unresolved channel** — what can't be confirmed gets PARKED with "basis +
   what to check next", not investigated forever.
5. **Encode-once** — the second time a review rejects the same class of
   mistake, STOP re-reviewing it: encode it as a test, ruff/eslint rule, CI
   check, or a CLAUDE.md/AGENTS.md line. Reviewers must never give the same
   feedback twice; that's paying for the same review in tokens.
6. **Commit per ticket** — a dead runner must never re-spend tokens on
   finished work.
7. **Model tiering** — cheap/fast models for mechanical stages; strong
   models only for the hardest design/verify steps.
