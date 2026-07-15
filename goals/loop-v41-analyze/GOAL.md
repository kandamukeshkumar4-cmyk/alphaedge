# Loop V41 — "AI Analyze" must actually analyze

> Runner: Cursor Grok 4.5 headless. Worktree E:/polymarket-worktrees/loop41-analyze,
> branch loop41/analyze. Orchestrator reviews every commit; NEEDS-FIX verdicts
> in STATE.md must be fixed before proceeding.

## THE BUG (user-reported, screenshot-verified)
Clicking "AI Analyze" on a market card opens the assistant with an analyze
prompt ("Analyze <title> for a paper trade. Current YES ~54¢."), the assistant
runs get_features successfully, then returns a CANNED CAPABILITY MENU ("I can
help with: ... Try asking: ...") instead of any analysis.

## ORCHESTRATOR DIAGNOSIS (verify, don't assume)
1. Prod Railway env has ZERO LLM keys (LLM_API_KEY / NIM_API_KEY default "").
   The assistant likely falls to a template when no LLM is configured.
2. Even keyless this is wrong: get_features SUCCEEDED — the data for an
   honest deterministic analysis exists (price/24h move, volume, drivers,
   model probability vs market price, brief if present, bear-case factors).

## Tickets (fix(loop41): <ticket>)
- A1 Diagnose in code (report first in STATE.md): trace the analyze-intent
  path in backend/app/api/v1/assistant.py + the agent it calls — confirm WHY
  the menu is returned (missing key fallback? intent router miss? both?).
- A2 Fix keyless path: when no LLM key, the analyze intent must return a REAL
  deterministic analysis composed from existing services (features, drivers,
  analyst brief if any, model prob vs market price, honest uncertainty note
  + paper-only disclaimer). Menu text remains ONLY for genuinely
  unrecognized intents. Never fabricate numbers — every figure from a real
  service call; omit sections whose data is absent (honestly noted).
- A3 LLM-present path: verify the same intent routes to the LLM properly
  when a key IS set (test with a fake/mock client — no real key needed).
  If routing was also broken, fix it.
- A4 Tests for all three states (keyless analyze, LLM analyze via mock,
  unrecognized intent -> menu) + full gate (COUNTS + ruff) + fresh verifier.
  STOP.
## Ownership: assistant/agent path + tests + goals/loop-v41-analyze/**;
claims for shared files. Frontend only if the panel mis-sends the intent
(check A1). PAPER_TRADING_ONLY; assistant stays analysis-only (no order
path); never push/merge.
