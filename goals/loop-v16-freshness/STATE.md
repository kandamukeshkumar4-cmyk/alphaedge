# Loop V16 — Data Freshness & Liveliness (STATE)

Read GOAL.md first. One ticket per iteration. Update EVERY iteration.
Runner: ChatGPT/Codex IDE (local) · worktree E:/polymarket-worktrees/loop16-fresh · branch loop16/freshness.
Orchestrator (Claude main thread) reviews every commit; never push/merge/deploy from here.

## MIGRATION CLAIMS (041+; check loop-v15 STATE.md claims too — 038/039/040 landed)

| Number | Claimed by | Ticket | Status |
|---|---|---|---|
| (none) | | | |

## SHARED FILE CLAIMS (routes.py / ws.py / db/models.py / schemas/** / workers/tasks.py)

| File | Ticket | Status |
|---|---|---|
| (none) | | |

## Tickets

| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| V1 | Trending ranks by recent activity; decided markets out | TODO | |
| V2 | Live Signals rail: named, valued, deduped | TODO | |
| V3 | Ticker freshness: DESC order, dedupe, age, 48h window | TODO | |
| V4 | F04 forecast auto-lock worker (unblocks grading) | TODO | new workers/forecast_autolock.py; claim tasks.py |
| V5 | Decided/closed market hygiene (no false LIVE chip) | TODO | |
| V6 | [LIVE] end-user re-test proof | TODO | prod READ-ONLY + local stack |

## LOOP LOG (append one entry per iteration; paste gate output tails)
