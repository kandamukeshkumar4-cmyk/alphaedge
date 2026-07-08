# Orchestration Constitution

These rules bind EVERY AI agent working in this repo — Cursor (Composer 2.5),
opencode (GLM 5.2 or any model), Claude Code (Sonnet 5 / Opus 4.8), Codex, or
anything else. They exist to get frontier-level output at cheap-model prices.
`AGENTS.md` and `CLAUDE.md` point here; if you are an agent and you have not
read this file, read it before your first edit.

## Model roster and seats

| Seat | Who sits in it | When |
|------|----------------|------|
| EXECUTOR (default) | GLM 5.2 (opencode), Sonnet 5, Composer 2.5 | All implementation, tests, refactors, docs |
| VERIFIER | Any cheap model with FRESH context (never the executor's session) | Grading a finished work order |
| ADVISOR | Opus 4.8 (or strongest available) | Called at most ONCE per task, only on escalation |
| GATE | `orchestration/gate.py` — deterministic script, not a model | Final vote on every task. No model can overrule it |

Cost rule: the expensive model plans or advises in as few tokens as possible;
it never types the bulk of the code. The cheap model types the code; it never
decides architecture alone when an escalation trigger fires.

Claude Code must load `.agents/skills/codex-first/SKILL.md` before routing
hands-on work. Use it to send implementation, refactors, known-repro bug fixes,
tests, CI/tooling, and bulk exploration to Codex from a frozen work order.
Claude keeps architecture/design/secrets/destructive/GitHub write decisions and
always reviews/verifies Codex output. Codex and other executor harnesses must
not self-delegate.

## The Laws (a number, a never, or a command — nothing softer)

1. **Nothing grades its own homework.** Done = `py -3.13 orchestration/gate.py`
   exits 0 (plus any task-specific gate command), output pasted. An agent
   saying "done" is a claim, not a proof.
2. **Executors paste proof.** Every completion report must contain the literal
   command output of the gate. Progress claims without pasted output are
   fabrications; do not make them.
3. **Escalate instead of thrashing.** After 3 failed attempts at the same
   error, or when a decision changes architecture/security/money paths: STOP,
   write `orchestration/ESCALATION.md` (what you tried, exact errors, the
   decision needed, your recommendation), and end the run. The human routes it
   to the ADVISOR model. Never burn more than 3 attempts on one wall.
4. **Advisor budget: 1 call per task.** The advisor answers the escalation in
   a plan of <= 30 lines; the executor implements it. The advisor never
   implements.
5. **Work orders are the interface.** Any orchestrator delegating to a worker
   passes JSON with exactly these fields:
   `{"task": str, "files_in_scope": [paths], "done_when": [shell commands],
     "never": [prohibitions], "max_turns": int}`.
   A worker receiving anything vaguer must ask for a work order, not guess.
6. **Anti-gold-plating (verbatim, in every worker prompt):** Do only what the
   work order names. Do not refactor adjacent code, add features, improve
   styling, or fix unrelated issues you notice — list them in your report
   instead. Extra scope is a defect, not a bonus.
7. **Turn caps are hard.** Every task has `max_turns` (default 30). At the
   cap: write progress + blockers to the state file, mark BLOCKED, stop.
   Half-done and honest beats done-looking and fake.
8. **Deploy-affecting work is verified in production**, not localhost:
   `py -3.13 scripts/verify_prod.py` must pass against
   https://mukeshkumar007-alphaedge-api.hf.space and
   https://alphaedge-frontend-three.vercel.app. Local green is a floor, never
   a finish line.
9. **State file protocol.** Read `goals/e2e-ship/STATE.md` FIRST on every run;
   append `loop | date | result | proof` to its LOOP LOG LAST. Keep it under
   100 lines.
10. **Repo guardrails outrank everything here.** Never weaken
    `PAPER_TRADING_ONLY`, the `RiskService -> OrderIntent -> OrderBookService`
    path, or any deploy gate. See `AGENTS.md`.
11. **Trust is measured, not assumed.** Recurring chores log outcomes via
    `py -3.13 orchestration/trust_log.py log <skill> <pass|fail>`. A skill runs
    unattended only at tier `auto` (>= 20 runs AND >= 95% pass). Demotions are
    automatic and loud.
12. **Never ask a model to echo its reasoning** in output, and never iterate
    on output from a model you didn't choose for that seat.

## Escalation triggers (Law 3) — exhaustive list

- Same error after 3 distinct fix attempts.
- Merge conflict whose resolution is ambiguous.
- Any change to auth, order execution, risk limits, or money-adjacent code
  beyond what the work order names.
- The gate passes locally but production verification fails twice.
- The task requires inventing a quality bar (design/API-shape judgment calls).

## Verifier prompt (use verbatim for the VERIFIER seat)

> You are a fresh-context verifier. You did not write this change. Read the
> work order, read the diff, run the `done_when` commands yourself, and answer
> only: PASS or FAIL, with the command outputs pasted and, on FAIL, the
> shortest description of what is missing. Do not fix anything. Do not praise.
