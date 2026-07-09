# LOOP 8 executor prompt (short form)

> **Canonical spec:** `goals/e2e-ship/LOOP8.md`  
> **Slash command:** `/loop8-vendor` (see `.claude/commands/loop8-vendor.md`)  
> **Loop type:** Goal-based (ClaudeDevs) — stop on acceptance gate OR 40 turns  
> **Seats:** Orchestrator plans/verifies · Executor implements · Advisor ≤1× on 3 failures

You are in `E:\polymarket clone`. Loop 8 closes report-parity gaps: toast flood, arb UI, Quest nav to Clones/Backtest, vendor MCP tools, honest empties. Loop 7-ux + report-ux-reconnect are DONE.

**Read first:** `goals/e2e-ship/LOOP8.md` → execute L8-T1…L8-T5 in order → run acceptance gate → update STATE.md → commit `loop8: report-parity vendor tools + quest surfaces`.

**Prod URLs:** frontend `https://alphaedge-frontend-three.vercel.app` · backend `https://mukeshkumar007-alphaedge-api.hf.space` · vendor clones `vendor-study/`

**Quick task list:**

| ID | Priority | Summary |
|---|---|---|
| **L8-T1** | P0 | Cap signal toasts ≤2; no remount flood on AI Analyze |
| **L8-T2** | P0 | Surface `/api/v1/arb` on `/signals` (honest empty OK) |
| **L8-T3** | P1 | Quest nav/links to Clones + Backtest (+ Feed/Track record) |
| **L8-T4** | P1 | 1–3 read-only MCP-style tools from vendor-study; ATTRIBUTIONS |
| **L8-T5** | P2 | Honest CLV/memories empty copy; owner BLOCKED unchanged |

**Acceptance (must paste):** `verify_prod.py` 6/6 · `verify_journey.py` 5/5 · frontend typecheck/lint/vitest/build · e2e local + live · backend pytest/ruff if touched · Vercel deploy · HF if backend changed · browser: AI Analyze usable, arb honest, clones/backtest reachable.

**Never:** fake data · weaken paper-trading · paste AGPL/unlicensed vendor code · enable ensemble without AutoLab · owner memory resolve without prod admin key.

**Max turns:** 40. On cap → BLOCKED in STATE.md.
