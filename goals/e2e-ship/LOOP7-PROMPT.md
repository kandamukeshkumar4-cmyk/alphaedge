# LOOP 7 of 7 — Close the last UX/feature gaps found by the 2026-07-08 end-to-end audit

You are working in `E:\polymarket clone`. Read `goals/e2e-ship/STATE.md` and this
file first. This loop is sized for smaller models: every task is narrow, has an
exact file list, and an exact proof command. Do the tasks IN ORDER. Maximum 40
turns; on cap, write BLOCKED into STATE.md and stop.

## Context — what the audit proved (do not re-verify, trust this)

Production is LIVE and healthy: `py -3.13 scripts/verify_prod.py` = 6/6,
`py -3.13 scripts/verify_journey.py` = 5/5, deployed e2e = 6/6 green.
Frontend: https://alphaedge-frontend-three.vercel.app · Backend:
https://mukeshkumar007-alphaedge-api.hf.space

Working (verified in the browser): homepage live pm- markets; market detail
chart + analyst brief + order book; /trade live terminal; /signals 50 live
signals; signup → live $100,000 paper balance; anon /portfolio redirects to
login. These are NOT to be touched except where a task below says so.

## Defects to fix (each was reproduced in the deployed UI)

### TASK 1 — ATLAS overlay blocks the page (HIGHEST priority)

The ATLAS AI panel auto-opens on EVERY page load and covers ~60% of the
viewport below ~800px width. It physically intercepted the click on the signup
Terms checkbox (signup was impossible until the panel was closed) and hides
homepage/leaderboard/signals content.

Fix in `frontend/src/context/atlas-panel.tsx` (and its consumers under
`frontend/src/components/quest/AtlasPanel.tsx`):
- Do NOT auto-open on page load. Default closed; open only on explicit user
  click of "Toggle ATLAS" (persist last state in `localStorage`, default closed).
- When open on viewports < 1024px, it must not overlap interactive content:
  render as a bottom sheet with a visible close affordance and `pointer-events`
  confined to the sheet.
- Never open on `/auth/*` routes.

Proof: `npm run typecheck && npm run lint` in `frontend/`, plus a Playwright
check (add to `frontend/e2e/app.spec.ts`): goto `/auth/signup`, assert the
terms checkbox is clickable without closing anything first.

### TASK 2 — Health banner false positive + market-detail sample-data fallback

A single transient HF-Space `429` made the deployed market-detail page show
"AlphaEdge API is unavailable. Showing sample data" plus mock-adapted values
("3,214 traders", "closes closed", "Paper market snapshot unavailable") for a
LIVE pm- market. One failed fetch must not flip the whole page to sample data.

Fix:
- `frontend/src/hooks/useApiHealth.ts` + `frontend/src/components/HealthBanner.tsx`:
  require 2 consecutive failures (or a failure persisting > 10s) before
  declaring "down"; a 429 is "degraded", not "down"; auto-recover on next
  success.
- `frontend/src/app/markets/[slug]/market-detail-client.tsx` (and the adapters
  in `frontend/src/lib/api-market-detail-adapter.ts`): when a slug is `pm-`/`ks-`
  and one endpoint fails, retry once with backoff and keep whatever live fields
  did load; only fall back to the mock catalog for genuinely unknown/seed slugs.
  Never print the mock "3,214 traders" style stats for a live slug — omit the
  stat instead.

Proof: `npm run typecheck && npm run lint && npx vitest run` in `frontend/`.

### TASK 3 — Header auth state stale after signup/login

After a successful signup the header still shows "Log in / Sign up". Fix
`frontend/src/components/SiteHeader.tsx` (and any auth context it reads) so
that after signup/login it shows the account state (email or avatar + log out)
without a hard refresh.

Proof: extend the signup Playwright spec — after creating a throwaway account
assert the header no longer contains "Sign up".

### TASK 4 — Leaderboard is an empty shell

Prod `GET /api/v1/leaderboard` returns `{"entries":[]}` and the page shows an
empty "Standings" card. Real users exist (journey verifier creates one per run
and places real paper orders).

- Backend: check why `entries` is empty (`backend/app/api/v1/leaderboard.py`
  or equivalent service). If the ranking requires resolved markets, add a
  fallback ranking over open positions/paper balance changes (label it
  "Provisional — unresolved markets"). NO fabricated traders.
- Frontend `frontend/src/app/leaderboard/page.tsx`: when entries are empty,
  render an honest empty state ("No ranked traders yet — rankings appear after
  markets resolve"), not a bare card.

Proof: `uv run --extra dev pytest -q tests/<leaderboard tests>` in `backend/`
+ frontend typecheck/lint. If backend change ships, deploy via push to
`codex/alphaedge-base` and paste the prod curl showing entries or the honest
empty payload.

### TASK 5 — Small honest-UX fixes (batch, keep each < 20 lines)

1. Signal toast cards show "Confidence —" (missing value): hide the Confidence
   row when the API gives none (`frontend/src/components/quest/QuestSignalRail.tsx`).
2. Bottom-nav label "GDP" for the portfolio page is opaque — rename the label
   to "Portfolio" (keep the route) in `frontend/src/components/BottomNav.tsx`.
3. Market-detail header for pm- slugs shows the raw slug as the breadcrumb
   title before hydration; show the market question once loaded (already
   available in the RSC payload — check `frontend/src/app/markets/[slug]/page.tsx`).

Proof: frontend typecheck + lint + vitest.

## Do-NOT list (guardrails)

- Never weaken `PAPER_TRADING_ONLY`, the RiskService→OrderIntent→OrderBookService
  order path, or any deploy gate.
- No fake data anywhere: no fabricated traders, memories, or confidence values.
- Do not touch `scripts/verify_prod.py` / `verify_journey.py` semantics.
- Owner-blocked items stay blocked (prod admin key for memories; Vercel token;
  LLM secret sync) — do not attempt workarounds.

## Ship + acceptance (end of loop)

1. `cd frontend && npm run typecheck && npm run lint && npx vitest run && npm run build`
2. `cd frontend && npx vercel --prod --yes` (frontend changes)
3. Backend changes (if any): commit + push to `codex/alphaedge-base`, wait for
   the HF deploy workflow to go green.
4. `py -3.13 scripts/verify_prod.py` → must stay 6/6.
5. `PLAYWRIGHT_BASE_URL=https://alphaedge-frontend-three.vercel.app E2E_LIVE=1 npm run e2e` → green.
6. Append a `7` row to the LOOP LOG in `goals/e2e-ship/STATE.md` with pasted
   outputs; commit `loop7: ux gap fixes from e2e audit`.
