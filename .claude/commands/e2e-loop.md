# /e2e-loop — one iteration of the E2E build loop

You are the implementer for the AlphaEdge E2E build loop. Your memory is
`goals/build-loop-e2e/STATE.md` — read it FIRST, fully, plus `AGENTS.md`.

Then do exactly one iteration:

1. Pick the first TODO, unblocked ticket. Say which and why in one line.
2. Implement the smallest slice that can go green. Reuse existing modules;
   match surrounding code style; UI must use the Quest tokens
   (tailwind.config.ts + globals.css CSS vars) and stay in the Questflow
   design language.
3. Run the FULL gate from STATE.md (backend pytest+ruff, frontend
   typecheck+lint+test+build, browser render for UI tickets). Fix until
   green. Do not weaken any test or guardrail to pass.
4. Spawn a SEPARATE verifier subagent (fresh context) to re-run the gate and
   adversarially review your diff against the guardrails in STATE.md.
   Its verdict is required before you may mark DONE.
5. Update STATE.md: ticket status + evidence in Notes, one AutoLab log line.
6. Commit: `feat(e2e-loop): <ticket-id> <summary>` (include the AutoLab line
   in the body). Do not push unless the remote workflow says to.

Absolute rules (from STATE.md, non-negotiable):
- PAPER_TRADING_ONLY; RiskService order path untouched.
- No FinceptTerminal code — clean-room ideas only (AGPL).
- No fabricated data/metrics. Demo fixtures only behind DemoChip when the
  API is empty. "Live-verified" claims require E01-style evidence.
- If a ticket needs something only the user has (Docker running, API tokens,
  election dataset), mark it BLOCKED-ON-USER/ENV with the exact ask — never
  simulate the missing piece.
- Stop after this one ticket. If 3 consecutive iterations made no ticket
  newly DONE, write a post-mortem in STATE.md and reorganize instead of
  attempting a 4th.
