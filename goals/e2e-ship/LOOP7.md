# LOOP 7 — UX gap closure (post–e2e audit)

**Status:** ACTIVE (executor runs this file + `LOOP7-PROMPT.md`)  
**Depends on:** Loop 6-final DONE (`verify_prod` 6/6, cron wired, acceptance green)  
**Goal:** Close the five UX defects found in the 2026-07-08 production browser audit so a real user can sign up, browse, trade, and read intelligence surfaces without mock-data false positives or blocked UI.

## Production URLs (canonical)

| Layer | URL |
|---|---|
| Frontend | https://alphaedge-frontend-three.vercel.app |
| Backend | https://mukeshkumar007-alphaedge-api.hf.space |
| Deploy branch | `codex/alphaedge-base` (backend + workflow YAML) |
| Frontend deploy | `cd frontend && npx vercel --prod --yes` |

## Audit matrix (2026-07-08 — ground truth)

What a user sees today **before** this loop's fixes ship:

| Route / surface | Verdict | Evidence |
|---|---|---|
| `/` homepage | **LIVE** | 300+ `pm-` market cards; no `alpha_quant`; verify_prod check 5 PASS |
| `/markets/[pm-slug]` | **LIVE** (fragile) | Chart, order book, LLM brief; transient 429 once flipped entire page to sample data |
| `/trade` | **LIVE** | Egypt FIFA market default; chart + order book; login gate honest |
| `/signals` | **LIVE** | 50+ real signals (price jump, weather edge, expiry fade) |
| `/auth/signup` | **BROKEN UX** | ATLAS auto-open covered Terms checkbox until manually closed |
| Header after signup | **STALE** | Still showed "Log in / Sign up" until hard refresh |
| `/leaderboard` | **EMPTY** | API `entries:[]` — SQL boolean bug + no honest empty copy |
| `/portfolio` (anon) | **HONEST** | Redirects to login |
| Signup → portfolio | **WORKS** | $100,000 paper balance on prod |
| `/memories` / Similar past | **BLOCKED** | Owner prod admin key — not in scope |
| Leaderboard API | **BUG** | `po.settled = 1` → Postgres ProgrammingError → silent `[]` |

**Not mock on money paths:** homepage catalog, trade terminal market picker, signals feed, analyst briefs, paper order API journey.

**Mock only when:** API truly unreachable (after debounced health banner) OR demo mode (no `NEXT_PUBLIC_API_URL`).

---

## Tasks (execute IN ORDER)

Each task has: **files**, **done_when**, **proof**. Stop and mark BLOCKED if a task needs owner secrets.

### L7-T1 — ATLAS must not block pages (P0)

**Problem:** ATLAS panel auto-opened on load, covered ~60% viewport, intercepted signup checkbox clicks.

**Files:**
- `frontend/src/context/atlas-panel.tsx`
- `frontend/src/components/quest/AtlasPanel.tsx`
- `frontend/e2e/app.spec.ts`

**Requirements:**
1. Default **closed** on first visit; never auto-open on mount.
2. Persist explicit user open/close in `localStorage` key `alphaedge.atlas.open` (`"1"` / `"0"`).
3. Force closed on all `/auth/*` routes.
4. Mobile (<1024px): when open, render as bottom sheet; close affordance visible; do not steal clicks from page content underneath.
5. Playwright: `/auth/signup` — terms checkbox checkable without closing anything (`force: false`).

**done_when:** typecheck + lint green; e2e spec `signup page is interactive: ATLAS never covers the terms checkbox` passes locally.

---

### L7-T2 — Debounced health + live-slug detail resilience (P0)

**Problem:** Single HF 429 showed red "API unavailable / sample data" and mock stats ("3,214 traders", "closes closed") on a live `pm-` market.

**Files:**
- `frontend/src/components/HealthBanner.tsx`
- `frontend/src/hooks/useApiHealth.ts` (header indicator only — banner is authoritative for "down")
- `frontend/src/app/markets/[slug]/market-detail-client.tsx`
- `frontend/src/lib/api-market-detail-adapter.ts`
- `frontend/src/app/markets/[slug]/page.tsx` (SSR `initialDetail` for title)

**Requirements:**
1. Health banner: **2 consecutive** failed probes before "down"; 429 → **degraded** (amber), not down; poll every 30s; auto-clear on recovery.
2. For `pm-` / `ks-` slugs: retry detail fetch twice with backoff; keep partial live fields; never show mock trader count or bogus "closes closed" for live slugs — omit stat instead.
3. Page `<h1>` shows market question from SSR/API, not raw slug, on first paint.

**done_when:** `npm run typecheck && npm run lint && npx vitest run` in `frontend/` green.

---

### L7-T3 — Header auth sync (P1)

**Problem:** After signup, header still showed anonymous "Sign up".

**Files:**
- `frontend/src/hooks/useAuth.ts` — dispatch/listen `alphaedge:auth-changed` on login/signup/logout
- `frontend/src/app/auth/signup/page.tsx` — call `saveAuthSession` helper
- `frontend/src/components/SiteHeader.tsx`

**Requirements:** Same-tab signup/login updates header to email + "Log out" without refresh.

**done_when:** Playwright live spec `header reflects auth state after signup without a refresh` passes when `E2E_LIVE=1`.

---

### L7-T4 — Leaderboard honest data (P1)

**Problem:** Prod leaderboard always empty due to SQL bug; page showed bare card or demo traders when API configured.

**Backend files:**
- `backend/app/api/v1/leaderboard.py` — use `po.settled IS TRUE` not `= 1` (Postgres boolean)
- `backend/tests/test_leaderboard.py`

**Frontend files:**
- `frontend/src/app/leaderboard/page.tsx` — when API configured and `entries.length === 0`, show honest empty state; demo rows **only** when `!API_BASE`

**done_when:**
```bash
cd backend && uv run --extra dev pytest -q tests/test_leaderboard.py
cd backend && uv run --extra dev ruff check app/api/v1/leaderboard.py tests/test_leaderboard.py
```
If backend changed: push to `codex/alphaedge-base`, wait HF deploy green, then:
```bash
curl -sS 'https://mukeshkumar007-alphaedge-api.hf.space/api/v1/leaderboard?limit=5'
```
Paste response (entries may still be empty if no resolved trades — that is OK if SQL no longer errors).

---

### L7-T5 — Small honest UX batch (P2)

| # | File | Change |
|---|---|---|
| 5a | `frontend/src/components/AlertToast.tsx` | Hide Confidence row when `confidencePct === null` |
| 5b | `frontend/src/components/BottomNav.tsx` | Label `"Portfolio"` not `"GDP"` (route stays `/portfolio`) |
| 5c | `frontend/src/components/SiteHeader.tsx` | Nav label `"Portfolio"` not `"GDP"` |
| 5d | `frontend/src/app/portfolio/page.tsx` | Page title `"Portfolio"`; kicker `"Unified paper portfolio"` |

**done_when:** frontend typecheck + lint + vitest green.

---

## Guardrails (never)

- Weaken `PAPER_TRADING_ONLY` or `RiskService → OrderIntent → OrderBookService`.
- Fabricate traders, memories, confidence, or leaderboard rows.
- Change `verify_prod.py` / `verify_journey.py` semantics to pass.
- Resolve owner-blocked memory loop without prod `ADMIN_API_KEY`.

## Owner BLOCKED (out of loop scope)

See `goals/e2e-ship/STATE.md` BLOCKED section: Vercel token, prod admin resolve curl, LLM secret sync if briefs regress to `fallback`.

---

## Acceptance gate (paste all outputs in STATE.md row `7-ux`)

Run from repo root unless noted.

```bash
# 1 — prod verifier unchanged
py -3.13 scripts/verify_prod.py

# 2 — journey still green (manual/dispatch only for cron)
py -3.13 scripts/verify_journey.py

# 3 — frontend quality
cd frontend && npm run typecheck && npm run lint && npx vitest run && npm run build

# 4 — local e2e (mock catalog)
cd frontend && npm run e2e

# 5 — deployed e2e (live API)
cd frontend && set PLAYWRIGHT_BASE_URL=https://alphaedge-frontend-three.vercel.app&& set E2E_LIVE=1&& npm run e2e

# 6 — backend floor (if backend touched)
cd backend && uv run --extra dev pytest -q && uv run --extra dev ruff check app tests
```

**Deploy:**
1. Frontend: `cd frontend && npx vercel --prod --yes`
2. Backend (if changed): commit + push to `codex/alphaedge-base`

**Close criteria:** All gates green; browser spot-check signup without closing ATLAS; market detail survives one 429 without sample-data banner; leaderboard shows honest empty OR real entries.

**STATE.md:** Append LOOP LOG row `7-ux` with pasted summaries. Final line must remain true:

> A user visiting the production URL sees live Polymarket/Kalshi markets, can complete the full paper-trading journey, and all intelligence surfaces are fed by production data.

If memories card still empty, note it as owner-blocked — does not falsify the sentence.

**Commit message:** `loop7: ux gap fixes from e2e audit`

**AutoLab:** not applicable (UX fixes, no iterative metric).  
**Bumblebee:** not applicable unless lockfiles/images change.

---

## Orchestration work order (for Codex / small models)

```json
{
  "task": "Execute goals/e2e-ship/LOOP7.md tasks L7-T1 through L7-T5 in order.",
  "files_in_scope": [
    "frontend/src/context/atlas-panel.tsx",
    "frontend/src/components/quest/AtlasPanel.tsx",
    "frontend/src/components/HealthBanner.tsx",
    "frontend/src/app/markets/[slug]/market-detail-client.tsx",
    "frontend/src/lib/api-market-detail-adapter.ts",
    "frontend/src/app/markets/[slug]/page.tsx",
    "frontend/src/hooks/useAuth.ts",
    "frontend/src/components/SiteHeader.tsx",
    "frontend/src/app/auth/signup/page.tsx",
    "frontend/src/app/leaderboard/page.tsx",
    "frontend/src/components/AlertToast.tsx",
    "frontend/src/components/BottomNav.tsx",
    "frontend/src/app/portfolio/page.tsx",
    "frontend/e2e/app.spec.ts",
    "backend/app/api/v1/leaderboard.py",
    "backend/tests/test_leaderboard.py",
    "goals/e2e-ship/STATE.md"
  ],
  "done_when": "All acceptance gate commands in LOOP7.md exit 0; STATE.md LOOP LOG row 7-ux appended with pasted proof.",
  "never": [
    "Fabricate data",
    "Weaken PAPER_TRADING_ONLY or order path",
    "Modify verify_prod/journey semantics",
    "Resolve memory loop without prod admin key"
  ],
  "max_turns": 40
}
```
