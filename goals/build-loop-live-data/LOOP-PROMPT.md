# /live-loop — one iteration of the Live-Data ("demo is real") loop

You are the implementer for the AlphaEdge Live-Data build loop. Your memory is
`goals/build-loop-live-data/STATE.md` — read it FIRST, fully, plus `AGENTS.md`
and the demo root-cause record in `goals/build-loop-opus48/STATE.md`.

The mission: the DEPLOYED site must show real, moving, populated data on every
core screen — no empty states, no "API error", no flat/zero charts, no
"Not Found". Seeded/replayed history is allowed to fill screens, but must be
labeled honestly (never shown as "Live").

Do exactly one iteration:

1. Pick the first TODO, unblocked ticket (R01 FIRST — it is a read-only audit
   that gates R02/R06; do not skip it). Say which and why in one line.
2. Implement the smallest slice that can go green. Reuse existing modules; match
   surrounding style; UI must use the Quest tokens + stay in the Questflow
   design language.
3. Run the FULL gate from STATE.md, INCLUDING the populated-demo smoke against a
   seeded LOCAL stack (Postgres + `alembic upgrade head` + the R02 seed +
   uvicorn). Fix until green. Never weaken a test/threshold/guardrail to pass.
4. Spawn a SEPARATE verifier subagent (fresh context) to re-run the gate and
   adversarially review the diff against the guardrails — especially the
   honest-labeling rule (no seeded row rendered under a green "Live" badge) and
   the no-benchmark-gaming rule. Verdict required before DONE.
5. Update STATE.md: ticket status + evidence, one AutoLab line.
6. Commit `feat(live-loop): <ticket-id> <summary>`, push, open/refresh the PR
   per the remote workflow.

Absolute rules (from STATE.md, non-negotiable):
- PAPER_TRADING_ONLY; RiskService order path untouched; no LLM order path.
- Honest data labeling: seeded/replay data may populate screens but is NEVER
  presented as live; "Live" only on a real in-window upstream tick.
- No fabricated-as-live metrics; no benchmark gaming; clean-room only.
- This container can't reach Polymarket/Kalshi/FRED/the HF Space. Verify locally
  against the seed. For anything requiring the real deployed backend, mark it
  BLOCKED-ON-DEPLOY with the exact command — NEVER simulate the live check or
  claim "live-verified" without real evidence from a reachable stack.
- Stop after this one ticket. After 3 consecutive no-progress iterations, write
  a post-mortem in STATE.md and reorganize instead of attempting a 4th.
