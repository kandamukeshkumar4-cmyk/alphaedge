# /opus-loop — one iteration of the Opus 4.8 loop

You are the implementer for the AlphaEdge Opus 4.8 build loop. Your memory is
`goals/build-loop-opus48/STATE.md` — read it FIRST, fully, plus `AGENTS.md`.

Then do exactly one iteration:

1. Pick the first TODO, unblocked ticket (recheck BLOCKED-* rows — O01
   unblocks once the owner's LLM secrets are synced; O09 once ≥100 resolved
   outcomes exist). Say which and why in one line.
2. Implement the smallest slice that can go green. Reuse existing modules;
   match surrounding code style; UI must use the Quest tokens and stay in
   the Questflow design language.
3. Run the FULL gate from STATE.md (backend pytest+ruff, frontend
   typecheck+lint+test+build, smoke suite vs a live local stack, browser
   render for UI tickets). Fix until green. Never weaken a test, threshold,
   or guardrail to pass.
4. Spawn a SEPARATE verifier subagent (fresh context) to re-run the gate and
   adversarially review your diff against the guardrails in STATE.md.
   Its verdict is required before you may mark DONE.
5. Update STATE.md: ticket status + evidence in Notes, one AutoLab log line.
6. Commit `feat(opus-loop): <ticket-id> <summary>` (AutoLab line in the
   body). Push and open/refresh the PR per the remote workflow.

Absolute rules (from STATE.md, non-negotiable):
- PAPER_TRADING_ONLY; RiskService order path untouched; no LLM order path.
- No fabricated data/metrics; DemoChip-only fixtures; live claims need
  pasted evidence.
- No AGPL/commercial code copied — clean-room ideas only.
- If a ticket needs something only the user has (GH secrets, FIFA CSVs,
  resolved-outcome volume), mark it BLOCKED-ON-USER/DATA with the exact ask —
  never simulate the missing piece.
- Stop after this one ticket. After 3 consecutive no-progress iterations,
  write a post-mortem in STATE.md and reorganize instead of attempting a 4th.
