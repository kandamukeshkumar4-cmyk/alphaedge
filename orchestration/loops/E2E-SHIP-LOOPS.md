# E2E Ship Loops — v3 (cost-optimized for cheap executors)

Paste one loop at a time into the executor agent (GLM 5.2 in opencode,
Composer 2.5, or Sonnet 5). Run strictly in order. Between loops, the human
reviews the commit and handles anything in `orchestration/ESCALATION.md`
(route escalations to the advisor model — Opus 4.8 — ONE call, answer <= 30
lines, executor implements).

Shared protocol (all loops): you are the EXECUTOR seat under
`orchestration/ORCHESTRATION.md` — read it first, plus `goals/e2e-ship/STATE.md`.
Do only what the work order names; list unrelated findings, never fix them.
After 3 failed attempts at one error, write `orchestration/ESCALATION.md` and
stop. At the turn cap, write BLOCKED to STATE.md and stop. Done means the
listed `done_when` commands exit 0 with output PASTED — nothing else counts.

---

## LOOP 0 — prod verifier + state

WORK ORDER
{"task": "Create goals/e2e-ship/STATE.md (PROD FACTS, LOOP LOG table, BLOCKED, NEXT) and scripts/verify_prod.py per the spec below, then run the verifier against production and record the result.",
 "files_in_scope": ["goals/e2e-ship/STATE.md", "scripts/verify_prod.py"],
 "done_when": ["py -3.13 scripts/verify_prod.py (checks 1-4,6 PASS; check 5 expected FAIL today — paste full output)"],
 "never": ["touch backend/ or frontend/ code", "mark check 5 as passing by weakening it"],
 "max_turns": 20}

verify_prod.py spec (stdlib only; --api and --frontend args; defaults below):
1. GET https://mukeshkumar007-alphaedge-api.hf.space/health -> 200 ok.
2. GET {api}/api/v1/markets?limit=300 -> >=200 markets; >=100 source=="polymarket"; >=5 source=="kalshi".
3. One open polymarket market's candles -> non-empty, source=="live".
4. GET {api}/api/v1/signals?limit=5 -> >=1 signal.
5. Frontend https://alphaedge-frontend-three.vercel.app homepage (fetch HTML, and the JS chunks it references) -> contains >=3 live "pm-" slugs AND not the string "alpha_quant". This is the anti-mock check.
6. GET {api}/api/v1/memories?limit=1 -> 200.
PASS/FAIL per check, nonzero exit on any failure.

---

## LOOP 1 — merge the backlog, deploy, confirm prod picked it up

WORK ORDER
{"task": "Get all completed-but-undeployed loop work into production. Fetch origin; find loop commits not in origin/codex/alphaedge-base (git cherry / branch --contains on loop3-agent-memory and loop2-ws-streams-event-bus); merge them into codex/alphaedge-base; gate locally; push. Backend auto-deploys via deploy-hf-space.yml — poll gh run list + prod /health + /api/v1/memories up to 20 min. For the frontend, use the deploy path for Vercel project 'alphaedge-frontend' recorded in goals/build-loop-ship/STATE.md; if it needs a token you don't have, write the exact command into STATE.md BLOCKED.",
 "files_in_scope": ["git branches", "goals/e2e-ship/STATE.md"],
 "done_when": ["py -3.13 orchestration/gate.py", "py -3.13 scripts/verify_prod.py (checks 1-4,6 PASS against prod)"],
 "never": ["resolve an ambiguous merge conflict by guessing — escalate", "deploy to any Vercel project named 'frontend'", "touch the dead Azure SWA or frontend-kappa-drab-22 URLs"],
 "max_turns": 35}

---

## LOOP 2 — kill the mock homepage (live-data-first frontend)

WORK ORDER
{"task": "The deployed homepage renders only 16 seed markets plus a fake 'Live trades' ticker (alpha_quant etc. from frontend/src/lib/mock-data.ts) while the API serves 185 open polymarket + 12 kalshi markets. Make every homepage surface (category rows, Trending, Top movers, New, Highest volume) feed from GET /api/v1/markets. Replace the fake ticker with real recent orders/signals, or remove it. mock-data.ts remains ONLY as the API-down fallback with the DemoChip indicator visible. Then deploy the frontend and verify on production.",
 "files_in_scope": ["frontend/src/**"],
 "done_when": ["py -3.13 orchestration/gate.py --frontend-only", "py -3.13 scripts/verify_prod.py (ALL checks incl. 5 PASS — paste output)"],
 "never": ["delete mock-data.ts", "ship invented usernames", "redesign styling"],
 "max_turns": 45}

---

## LOOP 3 — full user journey on a REAL market, in prod

WORK ORDER
{"task": "Write scripts/verify_journey.py (stdlib only) running entirely against prod: pick an open polymarket market -> detail 200 -> candles live -> AI brief 200 with rationale (warn-only if generator==fallback) -> signup/session via real auth contract -> place a small paper order -> position appears in portfolio. Fix any backend bug it exposes (fix locally, gate, push to codex/alphaedge-base, wait for HF deploy, re-run against prod). Then verify the same journey works in the deployed frontend UI for a pm- slug via /markets/view?slug=...",
 "files_in_scope": ["scripts/verify_journey.py", "backend/** (bug fixes only)", "frontend/** (bug fixes only)"],
 "done_when": ["py -3.13 scripts/verify_journey.py (all PASS against prod, paste output)", "py -3.13 scripts/verify_prod.py (all PASS)"],
 "never": ["fake a journey step", "bypass RiskService", "weaken PAPER_TRADING_ONLY"],
 "max_turns": 40}

---

## LOOP 4 — intelligence surfaces live: signals, briefs, ensemble, memory

WORK ORDER
{"task": "(1) Deployed /signals page renders the real prod signals. (2) A prod brief shows rationale + edge, and renders ensemble (n_models, stdev) and tools_used fields when present. (3) Memory write path: resolve ONE seed market via the admin resolve endpoint (X-Admin-API-Key; if the prod key is unavailable, write the exact curl into STATE.md BLOCKED) -> /api/v1/memories returns it -> 'Similar past markets' card renders. (4) Freshness heartbeat: two timestamped probes of candles/signals 15 minutes apart must differ; diagnose scheduler/Space-sleep if not.",
 "files_in_scope": ["frontend/src/**", "backend/** (fixes only)", "goals/e2e-ship/STATE.md"],
 "done_when": ["pasted deployed-signals evidence", "pasted prod brief payload", "pasted memories before/after (or BLOCKED entry)", "pasted two timestamped freshness probes", "py -3.13 orchestration/gate.py"],
 "never": ["insert fake memories", "fake timestamps"],
 "max_turns": 40}

---

## LOOP 5 — hardening: load, API-down honesty, loop heartbeat endpoint, mobile

WORK ORDER
{"task": "(1) 30 sequential GETs to prod /api/v1/markets?limit=300 -> all 200. (2) Confirm deployed frontend does multiplexed-WS/slow polling per Plan 007 — if prod still does 1s full-catalog polling the code never deployed; fix the deploy. (3) Build frontend against a dead API port and confirm every surface shows the sample-data indicator. (4) Add GET /api/v1/system/loops returning background_loop_plan + per-loop last heartbeat; push; verify in prod. (5) Playwright iPhone viewport against the deployed frontend: home, market detail, portfolio render without horizontal overflow.",
 "files_in_scope": ["backend/app/api/**", "frontend/src/**", ".github/workflows/** (only if deploy fix needed)"],
 "done_when": ["pasted 30-request status summary", "pasted prod /api/v1/system/loops response", "pasted Playwright mobile summary", "py -3.13 orchestration/gate.py", "py -3.13 scripts/verify_prod.py"],
 "never": ["redesign UI", "raise polling frequency"],
 "max_turns": 35}

---

## LOOP 6 — continuous verification + acceptance + close the books

WORK ORDER
{"task": "(1) Add verify_prod.py to demo-uptime.yml (30-min cron; failures fail the run; journey script stays manual — no junk orders on cron). (2) Acceptance, all against production: verify_prod, verify_journey, Playwright vs deployed URL, plus local gate. (3) Update goals/e2e-ship/STATE.md (LOOP LOG complete; BLOCKED = owner-only items with exact commands) and fix production URLs across README.md / docs/deploy/HUGGINGFACE_NEON.md / plans/README.md (frontend = alphaedge-frontend-three.vercel.app; Azure SWA is dead). (4) Register two standing goals if missing: goals/standing/prod-api-live.md and goals/standing/frontend-live-data.md (predicate: py -3.13 scripts/verify_prod.py). (5) Log this loop series outcome: py -3.13 orchestration/trust_log.py log e2e-ship pass|fail.",
 "files_in_scope": [".github/workflows/demo-uptime.yml", "goals/**", "README.md", "docs/**", "plans/README.md"],
 "done_when": ["all four acceptance outputs pasted", "py -3.13 orchestration/verify_goals.py exits 0", "closing sentence in STATE.md is TRUE per pasted evidence or replaced by the exact failing check"],
 "never": ["declare done without pasted production output"],
 "max_turns": 30}
