# Model Routing — Token Optimization for Claude Code

The orchestrator/executor split: one expensive model does the thinking
(planning, architecture, deciding what to delegate); cheaper models do the
executing (implementing a spec, running tests, collecting evidence). Without
this, every subagent inherits the main session's model — three subagents on a
Fable 5 session means three Fable 5 instances burning quota at $50/MTok output.

## The tiers

| Role | Model | $/MTok (in/out) | Assigned agents |
|---|---|---|---|
| Orchestrator (main brain) | Claude Fable 5 (session model picker) | $10 / $50 | The main session — plans, decomposes, delegates, reviews handoffs |
| Smart executor | `claude-opus-4-8` | $5 / $25 | `writer`, `implementer`, `verifier`, `reviewer`, `prediction-loop-runner` |
| Mid executor | `claude-sonnet-5` | $3 / $15 | `explorer`, `tester` |
| Lightweight checker | `claude-haiku-4-5` | $1 / $5 | `calibration-verifier`, `portfolio-monitor` |

Models are pinned in each agent's frontmatter (`.claude/agents/<name>.md` →
`model:` key). Subagents spawned via the built-in `Explore`/`general-purpose`
types still inherit the session model — prefer the named repo agents for
delegable work.

## Routing policy (for the orchestrator)

- **Keep on the main session (Fable 5):** architecture decisions, task
  decomposition, spec/brief writing, judging conflicting agent reports,
  anything touching `PAPER_TRADING_ONLY`, the order path, or deploy gates.
- **Route to Opus 4.8** (`writer`/`implementer`): any code change with a
  written brief or `explorer-notes.md`. Also `verifier`/`reviewer` — judgment
  calls on correctness and security stay one tier below the orchestrator, not
  three.
- **Route to Sonnet 5** (`explorer`/`tester`): codebase mapping and
  spec-derived test writing. Sonnet, not Haiku, because these need long-context
  recall across many files — the cheapest tier misses things and burns the
  savings in extra retry steps.
- **Route to Haiku 4.5** (`calibration-verifier`/`portfolio-monitor`): run one
  known command, parse the output, report PASS/FAIL. No judgment, no search.
- **Don't spawn a subagent at all** for a single-file read or a one-line grep —
  the orchestrator doing it directly is cheaper than any delegation.

## Effort levels

Model tier is the primary lever; effort is the secondary one.

- Main session: `xhigh` (Claude Code default) is right for the orchestrator.
- Delegated implementation: `high` is the sweet spot — lower effort means
  fewer, more consolidated tool calls with less preamble.
- Mechanical checkers: `low` — they follow a fixed script.

Workflow scripts can set this per agent call (`agent(prompt, {model, effort})`).

## Overriding

Routing steps aside on request. Say "run everything on Fable" or "don't use
subagents" in the prompt and the orchestrator works directly or passes a model
override when spawning. One-off overrides never get committed into the agent
frontmatter.

## Guardrail

Cheaper models change cost, never authority: every tier obeys AGENTS.md.
`PAPER_TRADING_ONLY`, the `RiskService → OrderIntent → OrderBookService` order
path, and deploy gates are non-negotiable at every price point, and a Haiku
checker's PASS/FAIL carries the same weight in the gate as anyone else's.
