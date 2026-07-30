# Loop E2E-FIX — repair pre-existing local-stack Playwright failures (2026-07-30)

> Orchestrator: Claude (Fable 5, resumed session). Executors: parallel
> diagnosis agents (one per failing spec) → implementer → verifier.
> Branch: `claude/missing-edge-thread-yqbqoc` (PR #58).

## Context

CI job "Local-stack Playwright" fails the SAME 5 specs deterministically on
the base branch (`codex/alphaedge-base`) and on every commit of PR #58
(whose diff is docs + static metadata routes + a workflow trigger — none of
these surfaces). The failures predate the PR and came out of frontend waves
104–117. Failure signatures are element-visibility timeouts.

## Tickets

| # | Ticket | Spec | Status |
|---|--------|------|--------|
| E1 | admin-eval: admin key via UI not in storage; stats; pause/unpause | e2e/admin-eval.spec.ts:67 | TODO |
| E2 | alpha: /alpha renders factor ledger + validated-factor report | e2e/alpha.spec.ts:19 | TODO |
| E3 | coachmarks: Getting started on first visit, persists dismiss | e2e/coachmarks.spec.ts:13 | TODO |
| E4 | loading-states: notification bell loading then honest state | e2e/loading-states.spec.ts:63 | TODO |
| E5 | marketplace: /library shows Trending + Featured above tabs | e2e/marketplace.spec.ts:86 | TODO |

## Method

1. Per spec: diagnosis agent reads the spec's selectors/expectations and the
   current components/pages it exercises; identifies the drift (renamed
   testid, moved section, changed copy, removed element) and whether the fix
   belongs in the SPEC (UI intentionally changed in waves 104–117) or in the
   UI (regression). Evidence required — file:line for both sides.
2. Implementer applies the smallest fix per ticket. Guardrails: never weaken
   an assertion to pass; if the UI regressed, fix the UI, not the test.
3. Gate: `npm run typecheck && npm run lint && npx vitest run && npm run build`
   green locally. Full Playwright verification happens in CI (local container
   has no Postgres service).

## Guardrails

PAPER_TRADING_ONLY untouched; no order-path changes; no fabricated data;
scope = frontend specs/components implicated by E1–E5 only.

## LOOP LOG

| iter | date | ticket | result | proof |
|------|------|--------|--------|-------|
