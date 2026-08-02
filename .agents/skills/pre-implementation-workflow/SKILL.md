---
name: pre-implementation-workflow
description: Contractor-style pre-implementation contract for any non-trivial change. Use before writing code for a new module, feature, bug fix, refactor, schema change, or migration. Investigate the repo before asking anything, then produce Goal / Blocking questions / Assumptions / Plan and stop for approval. Skip only for typo-class changes under ~20 lines with one clear solution.
---

# Pre-Implementation Workflow

Work like a contractor who pays for rework. Catch wrong assumptions early, and
don't make the user answer questions the repository already answers.

## 1. Investigate before asking

Read the relevant code, tests, configs, dependency manifests, and
documentation first. Search the repository and use the available tools before
asking the user anything. If the answer is discoverable in under a minute,
investigate it yourself.

Do not ask about the test framework, language version, lint rules,
error-handling conventions, directory layout, or existing abstractions when
the repository already answers them. If the codebase contradicts itself, or a
missing answer would change the design, raise it.

A question you could have answered by searching the repo is billed as rework.

## 2. Produce this, then stop

**Goal**
Restate the task in one paragraph in your own words, including the acceptance
criteria. If the restatement is wrong, this is the cheapest place to catch it.

**Blocking questions (0-3)**
Ask only when a wrong answer would force us to throw work away, not merely
adjust it. Include your recommended default with every question so the user
can reply "use all defaults." If nothing truly blocks the work, write "none."

**Assumptions**
Max five. Every assumption must be load-bearing: if being wrong wouldn't
change the design, delete it. List only specific, falsifiable assumptions,
covering only the areas this task touches:

- Data: shape, volume, trust level, encoding, and malformed inputs
- Failure: timeout, partial write, or downstream error; retry, fail loudly,
  or degrade
- Boundaries: callers, public vs. internal APIs, and backwards compatibility
- State: concurrency, idempotency, transactions, and ordering guarantees
- Environment: runtime version, deployment target, and allowed external access
- Scope: what you will not do and what remains TODO
- Testing: what you will test and what will remain uncovered

**Plan**
List the files you will create or modify, the key function or type
signatures, and the order of work. Where real alternatives exist, name the
rejected option and explain why in one clause.

Then stop. Do not implement.

## 3. Match the process to the risk

For a typo, rename, or an obvious change under ~20 lines with one clear
solution, skip the rest of this process and just do it.

For a new module, schema change, auth, money, migrations, or deletion, use
the full process.

For everything in between, one rule: if you can't say what makes a change
safe, treat it as risky.

## 4. After approval

Implement the plan as approved. If an assumption fails during implementation,
or the plan no longer fits the code, stop and tell the user. Do not switch
designs without telling them or continue with an approach you now believe is
wrong.

## 5. Prove it worked

Run the tests you promised in Assumptions and paste the output. List every
file you touched, with one line of why for each.

Change only what the plan names. A drive-by refactor is work the user didn't
order. Code without evidence is a claim, not a deliverable.

## AlphaEdge bindings

This skill composes with the repo's existing rules; it does not replace them:

- "Prove it worked" means the gate: done = `py -3.13 orchestration/gate.py`
  exit 0 with output pasted (`AGENTS.md` §3, `orchestration/ORCHESTRATION.md`).
- The "money / schema / auth" full-process tier includes anything touching
  `PAPER_TRADING_ONLY`, the `RiskService -> OrderIntent -> OrderBookService`
  path, or any deploy gate — those guardrails are never weakened.
- Blocking questions that change architecture, security, or money paths are
  escalations (`orchestration/ESCALATION.md`), not chat questions.
- Scope discipline in §5 is the same law as "extra scope is a defect" —
  list unrelated findings in the report, do not fix them.
