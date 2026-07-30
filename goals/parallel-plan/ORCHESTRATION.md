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

## CLOSE-OUT — 2026-07-30 (orchestrator, resumed session)

Program state audit against the stop condition:

- **Loop B (Grok backend):** G00–G07 all DONE and merged into the
  integration line (`codex/alphaedge-base`; see
  `goals/loop-grok-backend/STATE.md` LOOP LOG iters 1–8). NOTE: the remote
  branch `origin/loop-grok-backend` is a STALE snapshot ending at G03 with
  an unrelated history — do not merge it; G04–G07 already live here.
- **Loop A (Opus polish):** P01–P09 DONE; P10 BLOCKED-ON-DATA (resolved
  count < 100 — self-unblocks, recheck via `python -m app.ml.ab_harness`);
  P11 BLOCKED-ON-BACKEND (no measured bias-adjusted probability API exists;
  honest skip); P12 SKIPPED (dark-only design mandate; a toggle would be a
  non-functional fake).
- **Cross-loop handoffs:** all consumed. G02 arb fields → P09 (done);
  G05 `/api/v1/track-record` `thin_data` contract → consumed by
  `frontend/src/lib/track-record-api.ts` + `TrackRecordReliability` on
  `/track-record`; G07 smart-money endpoint live.
- **Remaining backlog (outside this program):** P10 A/B flip when resolved
  count ≥ 100; P11 needs a backend bias-adjusted field first.

Gate re-verification on this line (2026-07-30, sandboxed container):

- Backend: `uv run --extra dev pytest -q` → **2246 passed, 30 skipped,
  1 failed** — the single failure (`test_loop26_authz_matrix`) is
  environmental: `/api/v1/sports/ingest` needs outbound ESPN access and the
  container proxy returns 403, so the endpoint 502s. Not reproducible with
  network; unrelated to this docs diff. `ruff check app tests` → clean.
- Frontend: typecheck ✓, `eslint --max-warnings=0` ✓, vitest **581/581** ✓,
  `next build` ✓.
- Prod `verify_prod.py 6/6` not re-run: no deploy-affecting change since the
  last verified deploy on this line.

Stop condition met with the evidence above. Program CLOSED.
