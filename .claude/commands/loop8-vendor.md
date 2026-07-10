# /loop8-vendor — Report-parity + vendor-study integration (Loop 8)

You are the executor for **E2E Ship Loop 8**. Read these files first, in order:

1. `goals/e2e-ship/STATE.md` — prod facts, prior loop proof, BLOCKED owner items
2. `goals/e2e-ship/LOOP8.md` — canonical task list, ground truth, acceptance gate
3. `goals/e2e-ship/LOOP8-PROMPT.md` — short executor reminder
4. `AGENTS.md` — guardrails

## Your job

Execute tasks **L8-T1 → L8-T5** from `LOOP8.md` **in order**. Each task is narrow; do not expand scope.

1. **L8-T1** — Signal toast flood ≤2; remount-safe; AI Analyze usable
2. **L8-T2** — Arb opportunities on `/signals` (honest empty when none)
3. **L8-T3** — Quest reaches Clones / Backtest (nav or Discover links)
4. **L8-T4** — 1–3 read-only tools from vendor-study MCP repos + ATTRIBUTIONS
5. **L8-T5** — Honest CLV/memories empty copy

After all tasks: run the **Acceptance gate** block in `LOOP8.md` (paste every summary).

Deploy:
- Frontend changes → `cd frontend && npx vercel --prod --yes`
- Backend changes → push to `codex/alphaedge-base`, wait HF deploy green

Update `goals/e2e-ship/STATE.md`:
- Append LOOP LOG row `8-vendor` with result + pasted proof
- Do **not** remove owner BLOCKED items

Commit: `loop8: report-parity vendor tools + quest surfaces`

## Hard stops

- **40 turns max** — write BLOCKED to STATE.md and stop
- **3 failures on same error** — write `orchestration/ESCALATION.md` per ORCHESTRATION.md
- Never fabricate traders, memories, CLV, arb rows, or confidence
- Never weaken `PAPER_TRADING_ONLY` or the order path
- Never paste AGPL (homerun) or unlicensed arb source into the tree

## Task argument

$ARGUMENTS
