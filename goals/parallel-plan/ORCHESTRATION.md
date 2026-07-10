# Parallel Loop Orchestration — PM contract (2026-07-09)

Orchestrator: Claude (Fable 5, main thread). Pattern: "plan big, execute
small" — the orchestrator plans, monitors, reviews, and merges; executors
burn the tokens (ClaudeDevs advisor/orchestrator pattern, 2026-07-06/07).

## The two loops

| Loop | Executor | Worktree / branch | Owns | Loop file |
|------|----------|-------------------|------|-----------|
| A: Polish | Claude Opus 4.8 | `E:\polymarket-worktrees\loop-opus-polish` / `loop-opus-polish` | `frontend/**` | `goals/build-loop-polish/STATE.md` via `goals/loop-opus-polish/ASSIGNMENT.md` |
| B: Backend | Grok 4.5 (Cursor) | `E:\polymarket-worktrees\loop-grok-backend` / `loop-grok-backend` | `backend/**` (+ vendor study in `E:\polymarket-vendor`) | `goals/loop-grok-backend/STATE.md` |

## Non-collision rules

1. Disjoint file ownership (frontend vs backend); disjoint goals/ folders;
   neither touches scripts/, orchestration/, .github/, root configs.
2. Backend API changes are additive-only, documented in
   `goals/loop-grok-backend/API-NOTES.md`; the polish loop reads that file
   (never edits) to integrate.
3. Executors commit to their own branch only; never push, never merge, never
   rebase. Orchestrator merges into `loop3-agent-memory` (frontend/Vercel
   line) and `codex/alphaedge-base` (backend/HF deploy line) after review.

## Orchestrator duties (each check-in)

1. `git -C <worktree> log --oneline -5` + read each loop's LOOP LOG delta.
2. On a new DONE ticket: fresh-context diff review vs guardrails
   (PAPER_TRADING_ONLY, order path, no fabricated data, scope fence).
3. If clean: merge to the right integration branch; deploy-affecting merges
   require `py -3.13 scripts/verify_prod.py` 6/6 after deploy.
4. Cross-loop handoffs: when G02/G05/G07 land, tell Loop A which UI ticket
   unblocks (P09 arb fields, P07/P11 track-record, smart-money page).
5. If a loop stalls (ESCALATION.md, 3 no-progress iterations, or scope-fence
   breach): stop it, post-mortem, reassign or re-scope the ticket.
6. Stop condition for the whole program: both loops' tickets DONE or BLOCKED,
   merged, prod 6/6 green.
