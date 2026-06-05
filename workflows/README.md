# Workflows

Reusable execution procedures for AlphaEdge. A **goal** (`/goals`) says *what* to build; a **workflow** says *how* to build, verify, and hand it off. Goals bind to a workflow by name so the process never has to be re-derived per task.

## Index

| Workflow | Use for |
|---|---|
| [backend-feature](backend-feature.workflow.md) | Any `backend/app` change (connectors, signals, services, models, migrations) |
| [ui-feature](ui-feature.workflow.md) | Any `extension/` or `frontend/` change |
| [clv-model-gate](clv-model-gate.workflow.md) | Any predictive model — enforces beat-the-closing-line before it's shown as edge |

## Shared Definition of Done (every goal)

A goal is **not** done until all of these hold:

1. The goal's **acceptance gate** is met and proven by a runnable command.
2. **Verification passes** (the commands in the workflow + `local.config.json` `verificationCommands`).
3. **Safety intact:** `PAPER_TRADING_ONLY=true`; no real-money/execution wording; no wallet/private-key storage; `RiskService → OrderIntent → OrderBookService` is the only order path; LLM/sentiment never sets a stake, side, or `is_edge`.
4. **Review gate:** `requesting-code-review` skill (or explicit manual-diff fallback) per `AGENTS.md`; `bumblebee-supply-chain-scan` if any dependency manifest/lockfile changed.
5. **Scope honesty:** the PR claims only this phase's gate, not later ones.
6. The goal's **status** is updated in [/goals/README.md](../goals/README.md) and the **PR/handoff line** (below) is recorded.

## PR / handoff line

```text
Phase <n> <name> | gate=<met/blocked> | verify=<commands + pass counts> | safety=<paper-only, no-exec, no-keys: ok> | review=<skill/manual> | AutoLab=<line or n/a>
```

For improvement tickets (a measurable metric), the `AGENTS.md` AutoLab persistence loop applies and its line is required.
