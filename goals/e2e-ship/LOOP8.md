# LOOP 8 — Report-parity close + vendor-study integration

**Status:** ACTIVE (executor runs this file + `LOOP8-PROMPT.md`)  
**Depends on:** Loop 7-ux DONE + `report-ux-reconnect` DONE (`verify_prod` 6/6)  
**Loop type (ClaudeDevs):** Goal-based (`/goal`) — stop when acceptance gate exits 0 OR 40 turns  
**Orchestration (ClaudeDevs):** Orchestrator plans/verifies; executor (Grok 4.6 / Sonnet / Codex) implements frozen work orders; advisor at most once on 3× same failure  

**Goal:** Close the remaining gaps between the technical report vision and the live product: (1) signal-toast flood fixed on prod, (2) Quest UI surfaces report Tier-1 features that already exist in the backend, (3) vendor-study Tier-1 repos yield concrete read-only improvements, (4) honest empty states for CLV/memories/arb — no fabricated data.

## Production URLs (canonical)

| Layer | URL |
|---|---|
| Frontend | https://alphaedge-frontend-three.vercel.app |
| Backend | https://mukeshkumar007-alphaedge-api.hf.space |
| Deploy branch | `codex/alphaedge-base` (backend + workflow YAML) |
| Frontend deploy | `cd frontend && npx vercel --prod --yes` |
| Vendor clones | `vendor-study/` (gitignored; 16 repos already present) |

## Ground truth (2026-07-09 — before this loop ships)

| Surface | Verdict | Evidence |
|---|---|---|
| Homepage / markets / trade | **LIVE** | verify_prod 6/6; 321 pm- + 18 ks- |
| `/signals` | **LIVE** | 50 rows on `/api/v1/signals/dashboard` |
| AI Analyze / briefs | **LIVE** | LLM + tools_used; toast flood can obscure panel |
| Signal toasts | **BROKEN UX** | Opening ATLAS remounts header → backlog of `delta:price_jump` toasts |
| Cross-market arb API | **LIVE empty** | `/api/v1/arb` returns `signal_only:true`, often `opportunities:[]` |
| Arb in Quest UI | **MISSING** | API exists; not surfaced on `/signals` or market detail |
| `/clones`, `/backtest`, `/feed` | **BUILT** | Loop C U02/U06/U10 — not primary Quest nav |
| CLV track record | **HONEST EMPTY** | `clv_records:[]` until resolutions |
| Memories / similar past | **BLOCKED** | `items:[]` — needs owner prod admin key |
| Ensemble / retrieval flags | **OFF** | Code present; leave OFF unless AutoLab proves win |
| vendor-study usage | **PARTIAL** | ~8–10 repos influenced backend; MCP/arb UI gaps remain |

**Report Tier-1 already in backend (do NOT rebuild):** streams, clone-lite, decision/brief surfaces, arb_service, native MCP-style `tools.py`, paper CLOB + risk path.

---

## How this loop was designed (from ClaudeDevs threads)

| Thread idea | Applied here |
|---|---|
| **Goal-based loop** — stop on verifiable criteria + turn cap | Acceptance gate + `max_turns: 40` |
| **Deterministic verification** | Every task has `proof` commands; paste outputs in STATE |
| **Orchestrator + executor** | Spec frozen in this file; executor implements only `files_in_scope` |
| **Advisor rare** | Escalate once after 3 failures on same error → `orchestration/ESCALATION.md` |
| **Encode quality into the system** | Toast cap, honest empties, attributions — not one-off patches |
| **Scripts for deterministic work** | Prefer `verify_prod.py` / pytest over agent judgment |
| **Do not over-loop** | No ensemble/retrieval ON without measured Brier win |

---

## Tasks (execute IN ORDER)

Each task: **files**, **requirements**, **done_when**, **proof**. Stop and mark BLOCKED if owner secrets required.

### L8-T1 — Signal toast flood must not block AI Analyze (P0)

**Problem:** Clicking ✦ AI Analyze remounts SiteHeader; `useSignalAlerts` + `AlertToast` dump every unread `price_jump` as stacked red cards.

**Files:**
- `frontend/src/hooks/useSignalAlerts.ts`
- `frontend/src/components/AlertToast.tsx`
- `frontend/src/components/SiteHeader.tsx` (only if needed)

**Requirements:**
1. Cap visible toasts to **≤2** newest signals.
2. Persist “already shown” across remounts (module-level set or equivalent).
3. Advance `alphaedge.lastSignalTs` watermark after toasting so backlog does not re-flood.
4. Opening ATLAS / AI Analyze must not cover the panel with a toast stack.

**done_when:** typecheck + lint green; manual or Playwright: open AI Analyze → ≤2 toasts, ATLAS usable.

**proof:**
```bash
cd frontend && npm run typecheck && npm run lint
```

---

### L8-T2 — Surface cross-market arb in Quest UI (P0)

**Problem:** `/api/v1/arb` exists and is signal-only; Quest `/signals` and market detail never show opportunities when present.

**Files:**
- `frontend/src/app/signals/page.tsx`
- `frontend/src/lib/` (new thin arb client if needed, e.g. `arb-api.ts`)
- `backend/app/api/v1/arb.py` (read-only; only if response shape blocks FE)
- Study only: `vendor-study/taetaehoho__poly-kalshi-arb/` (ideas; no paste of unlicensed code)

**Requirements:**
1. Fetch arb opportunities from live API on `/signals` (or a dedicated panel).
2. When `opportunities.length === 0`, show honest empty: “No cross-platform arb signals right now” — never fabricate rows.
3. When opportunities exist, show platform pair, edge, and link to markets — label **signal only / paper**.
4. Do not auto-trade or call order path.

**done_when:** typecheck + lint + vitest green; curl arb API + UI empty/live states match.

**proof:**
```bash
curl -sS 'https://mukeshkumar007-alphaedge-api.hf.space/api/v1/arb/opportunities?limit=5'
cd frontend && npm run typecheck && npm run lint && npx vitest run
```

---

### L8-T3 — Quest nav reaches report Tier-1 surfaces (P1)

**Problem:** Clone-lite, backtest, feed, and decision surfaces exist but Quest primary nav hides them → product feels incomplete vs report.

**Files:**
- `frontend/src/components/SiteHeader.tsx`
- `frontend/src/components/BottomNav.tsx` (if mobile)
- Optionally thin landing cards on Discover linking to `/clones`, `/backtest`, `/feed`, `/track-record`

**Requirements:**
1. Desktop nav includes at least: Discover, Trade, Markets, Signals, **Clones**, Portfolio (Leaderboard may stay).
2. Or: Discover page has one clear “Intelligence” section with links to Clones / Backtest / Track record / Feed — not a dashboard clutter bomb (one job per section).
3. Preserve Quest visual language; no GDP labels; paper-trading disclaimer intact.

**done_when:** typecheck + lint green; browser: each linked route loads without Application error.

**proof:**
```bash
cd frontend && npm run typecheck && npm run lint
# Spot-check: /clones /backtest /feed /track-record /signals
```

---

### L8-T4 — Vendor-study MCP tool gap-fill (P1)

**Problem:** Report called for MCP servers; native `tools.py` has order book / history / whale — PolyMarket-MCP and polymarket-agents still have unused read-only patterns.

**Files:**
- `backend/app/agents/tools.py`
- `backend/tests/` (focused tool tests)
- `docs/ATTRIBUTIONS.md`
- Study: `vendor-study/guangxiangdebizi__PolyMarket-MCP/`, `vendor-study/artvandelay__polymarket-agents/`, `vendor-study/berlinbra__polymarket-mcp/`

**Requirements:**
1. Diff vendor READMEs/tools vs current `tools.py`.
2. Add **1–3 read-only** tools max (examples: depth skew, whale concentration %, recent trade intensity) — compact dict return, never raise, never touch RiskService/OrderBookService write path.
3. Wire into analyst tool list so fresh briefs can show new `tools_used` chips when used.
4. Update `docs/ATTRIBUTIONS.md` with what was adapted (MIT) vs ideas-only.
5. Refresh shallow clones if stale: `git -C vendor-study/<dir> pull --ff-only` (optional).

**done_when:**
```bash
cd backend && uv run --extra dev pytest -q tests/test_analyst_agent.py
cd backend && uv run --extra dev ruff check app/agents/tools.py tests/
```

If backend changed: push to `codex/alphaedge-base`, wait HF deploy green, then trigger one prod brief and confirm `tools_used` includes new tool(s) OR existing tools still present.

---

### L8-T5 — Honest intelligence empties + owner BLOCKED doc (P2)

**Problem:** CLV empty and memories empty look like bugs; report expected track-record + memory cards.

**Files:**
- `frontend/src/app/signals/page.tsx` (CLV section copy)
- `frontend/src/app/track-record/page.tsx` (if disconnected)
- `goals/e2e-ship/STATE.md` BLOCKED section (clarify owner curl)
- Do **not** fabricate CLV or memories

**Requirements:**
1. CLV empty copy: “No resolved CLV records yet — appears after markets resolve.”
2. Memories / Similar past: if API returns `total:0`, show owner-blocked honest message (not “Failed to fetch”).
3. Document in STATE that owner must run prod admin resolve curl (unchanged secret).

**done_when:** frontend typecheck + lint green; no fake rows in UI.

---

## Guardrails (never)

- Weaken `PAPER_TRADING_ONLY` or `RiskService → OrderIntent → OrderBookService`.
- Fabricate traders, memories, CLV, arb rows, or confidence.
- Paste AGPL (homerun) or unlicensed arb source into the tree — clean-room / MIT only.
- Import live-execution / wallet / copy-trade code from any vendor-study repo.
- Flip `ENSEMBLE_ENABLED` / retrieval ON without AutoLab measured win.
- Change `verify_prod.py` / `verify_journey.py` semantics to pass.
- Resolve owner-blocked memory loop without prod `ADMIN_API_KEY`.

## Owner BLOCKED (out of loop scope)

See `goals/e2e-ship/STATE.md` BLOCKED #2 — prod admin seed resolve for memories.  
Optional: clone `orcalayer` into `vendor-study/` for a future loop (not required for L8 close).

---

## Acceptance gate (paste all outputs in STATE.md row `8-vendor`)

```bash
# 1 — prod verifier
py -3.13 scripts/verify_prod.py

# 2 — journey
py -3.13 scripts/verify_journey.py

# 3 — frontend quality
cd frontend && npm run typecheck && npm run lint && npx vitest run && npm run build

# 4 — local e2e
cd frontend && npm run e2e

# 5 — live e2e
cd frontend && set PLAYWRIGHT_BASE_URL=https://alphaedge-frontend-three.vercel.app&& set E2E_LIVE=1&& npm run e2e

# 6 — backend (if touched)
cd backend && uv run --extra dev pytest -q && uv run --extra dev ruff check app tests
```

**Browser spot-check (required):**
1. Click ✦ AI Analyze → ATLAS opens; ≤2 signal toasts; panel usable.
2. `/signals` shows live signals + honest arb empty OR real arb rows.
3. Nav/links reach `/clones` and `/backtest` without Application error.
4. No red “sample data” banner under normal API.

**Deploy:**
1. Frontend: `cd frontend && npx vercel --prod --yes`
2. Backend (if L8-T4 changed): commit + push `codex/alphaedge-base`; wait HF green

**Close criteria:** All gates green; toast flood gone; arb surfaced honestly; Quest reaches Clones/Backtest; vendor tools attributed; memories still owner-blocked OK.

**STATE.md:** Append LOOP LOG row `8-vendor` with pasted summaries. Keep final sentence true:

> A user visiting the production URL sees live Polymarket/Kalshi markets, can complete the full paper-trading journey, and all intelligence surfaces are fed by production data.

**Commit message:** `loop8: report-parity vendor tools + quest surfaces`

**AutoLab:** not applicable unless L8-T4 flips ensemble (forbidden without measure).  
**Bumblebee:** not applicable unless lockfiles/images change.

---

## Orchestration work order (for Grok 4.6 / Codex / small models)

```json
{
  "task": "Execute goals/e2e-ship/LOOP8.md tasks L8-T1 through L8-T5 in order.",
  "executor": "Grok 4.6 or Codex",
  "orchestrator": "Claude/Cursor parent — reviews diffs and runs Phase acceptance",
  "files_in_scope": [
    "frontend/src/hooks/useSignalAlerts.ts",
    "frontend/src/components/AlertToast.tsx",
    "frontend/src/components/SiteHeader.tsx",
    "frontend/src/components/BottomNav.tsx",
    "frontend/src/app/signals/page.tsx",
    "frontend/src/lib/arb-api.ts",
    "frontend/src/app/page.tsx",
    "backend/app/agents/tools.py",
    "backend/tests/test_analyst_agent.py",
    "docs/ATTRIBUTIONS.md",
    "goals/e2e-ship/STATE.md",
    "vendor-study/"
  ],
  "done_when": "All acceptance gate commands in LOOP8.md exit 0; STATE.md LOOP LOG row 8-vendor appended with pasted proof.",
  "never": [
    "Fabricate data",
    "Weaken PAPER_TRADING_ONLY or order path",
    "Paste AGPL/unlicensed vendor source",
    "Enable ensemble/retrieval without AutoLab win",
    "Modify verify_prod/journey semantics",
    "Resolve memory without prod admin key"
  ],
  "max_turns": 40,
  "advisor": "Call once only after 3 failures on the same error; write orchestration/ESCALATION.md"
}
```

## Prompt header (paste before each executor session)

```text
You are the executor for AlphaEdge Loop 8 at E:\polymarket clone.
Read goals/e2e-ship/LOOP8.md. Implement only the current task's files_in_scope.
Run every proof command and paste output. Do not commit unless asked.
Paper-trading only. No live execution from vendor-study repos.
```
