# /loop7-ux — Close post-audit UX gaps (Loop 7)

You are the executor for **E2E Ship Loop 7**. Read these files first, in order:

1. `goals/e2e-ship/STATE.md` — prod facts, prior loop proof, BLOCKED owner items
2. `goals/e2e-ship/LOOP7.md` — canonical task list, audit matrix, acceptance gate
3. `goals/e2e-ship/LOOP7-PROMPT.md` — short executor reminder
4. `AGENTS.md` — guardrails

## Your job

Execute tasks **L7-T1 → L7-T5** from `LOOP7.md` **in order**. Each task is narrow; do not expand scope.

1. **L7-T1** — ATLAS default closed; never on `/auth/*`; signup checkbox reachable
2. **L7-T2** — Debounced health banner; live-slug detail must not flip to mock on one 429
3. **L7-T3** — Header updates after signup/login without refresh
4. **L7-T4** — Leaderboard SQL fix + honest empty state (no fake traders when API live)
5. **L7-T5** — Portfolio label, AlertToast confidence, page titles

After all tasks: run the **Acceptance gate** block in `LOOP7.md` (paste every summary).

Deploy:
- Frontend changes → `cd frontend && npx vercel --prod --yes`
- Backend changes → push to `codex/alphaedge-base`, wait HF deploy green

Update `goals/e2e-ship/STATE.md`:
- Append LOOP LOG row `7-ux` with result + pasted proof
- Do **not** remove owner BLOCKED items

Commit: `loop7: ux gap fixes from e2e audit`

## Hard stops

- **40 turns max** — write BLOCKED to STATE.md and stop
- **3 failures on same error** — write `orchestration/ESCALATION.md` per ORCHESTRATION.md
- Never fabricate traders, memories, or confidence values
- Never weaken `PAPER_TRADING_ONLY` or the order path

## Task argument

$ARGUMENTS
