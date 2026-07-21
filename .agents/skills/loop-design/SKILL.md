---
name: loop-design
description: >
  How to design an agent LOOP instead of writing one-off prompts. Auto-load
  before authoring any multi-step/parallel/long-running agent task, runner
  brief, orchestration plan, or "loop" (loop-vNN GOAL). Turns a vague ask into
  a goal+rubric -> plan -> parallel workers -> unbiased verifier -> stop
  condition harness. Applies to every agent in this repo (Claude Code, Codex,
  Cursor, opencode/GLM/Kimi, Grok) from any thread or IDE.
---

# Loop design — stop prompting, design the loop that prompts the agent

Source principle (Steinberger/OpenAI, Cherny/Anthropic, 2026): the leverage
moved from *typing prompts* to *designing loops*. A prompt is a question
answered once. A loop is a job — the agent keeps working, checks its own
progress, and continues until a **verified outcome**, not until it emits an
answer. Every agent harness (Claude Code, Cursor, Codex) is already a loop
underneath; this repo makes the loop explicit and author-controlled instead of
hidden.

Do NOT install any third-party loop engine (e.g. Slate/`@randomlabs/slate`) to
get this — this repo's worktree + gate + STATE.md + routing harness already
implements every block below. This skill is the discipline, not a tool.

## When to use

Authoring a `goals/loop-vNN/GOAL.md`; briefing a runner (Codex/Grok/Cursor/
opencode); planning multi-step, parallel, or 24/7 work; any task where "answer
once" is not enough. For a genuine one-shot fix, skip this — just do it.

## The eight blocks of a good loop (wire the ones the task needs)

1. **Goal input + success rubric.** State the objective AND the observable
   exit criterion in the same breath. "Fix X" is a prompt; "X does Y,
   proven by test/command Z, DONE-or-BLOCKED in STATE.md" is a loop goal.
2. **Planner.** Break the job into ordered, independently-verifiable tickets
   (A1..An). Each ticket is itself a small goal with its own done-check.
3. **Parallel workers.** Independent tickets run in separate worktrees, one
   runner each, exclusive file charters — never two agents on one file. See
   the orchestration constitution.
4. **Unbiased verifier.** The agent that wrote the code never certifies it.
   Verification is an independent pass (a fresh gate run, a separate reviewer
   agent) that returns a verdict against the rubric, not the author's word.
   "Done" = `py -3.13 orchestration/gate.py` exit 0 with output pasted.
5. **Model per step.** Route each step to the cheapest model that can do it;
   reserve frontier models for the hardest reasoning/verify steps. Follow the
   routing table in `.claude/LOOP_GUIDE.md` (mechanical/docs -> Grok; UI ->
   GLM/Cursor; migrations/design/review -> strong model; signal reasoning ->
   the configured Nemotron tier). A model too weak for a step burns tokens
   failing; a model too strong for a trivial step burns tokens needlessly.
6. **State.** Persist progress so a dead runner never re-pays for finished
   work: commit per ticket, write STATE.md, use the memory files and the
   research vault. Resume from state, don't restart.
7. **Stop condition.** Every loop declares when it ends: "stop when A1..An
   DONE or BLOCKED in STATE.md" plus the caps from the token-budget law
   (finding/round caps, 3-strikes -> ESCALATION.md, K=3 no-progress). No
   uncapped "be thorough" loops.
8. **Self-diagnose + grow.** When a loop stalls or a review rejects the same
   class of mistake twice, don't re-run it unchanged — add a block (a test, a
   lint/CI check, a CLAUDE.md/AGENTS.md line) so the next loop is smarter.
   Encode-once; reviewers never give the same feedback twice.

## Authoring checklist (put this in the GOAL/brief)

- [ ] Objective + observable success rubric stated together
- [ ] Ordered tickets, each independently verifiable, one commit each
- [ ] File charter per parallel worker (no overlap)
- [ ] Verification is independent of the author, defined as a runnable command
- [ ] Model chosen per step per the routing table
- [ ] State/resume: commit-per-ticket + STATE.md
- [ ] Explicit stop condition + caps (token-budget law)
- [ ] Guardrails from AGENTS.md §1 precedence restated where money/orders/
      paper-trading are touched

## Anti-patterns (these are prompts wearing a loop costume)

- A goal with no exit criterion ("make it better") — never terminates cleanly.
- The author grading its own output — not verification.
- One model for every step — wastes tokens at both ends.
- No commit until the end — a crash loses everything and re-pays.
- "Ultra"/fan-out with no cap — a token bonfire; capped rounds only.
