# STATE-SEARCHUI — Loop V91 FRONTEND node (search UI)

Branch: `loop91/search-ui` · Worktree: `E:/polymarket-worktrees/loop91-searchui`
Charter (touched NOTHING else):

- `frontend/src/lib/search-api.ts` (+ its test file, required by the SU1 proof command)
- `frontend/src/components/search/**` (new surface)
- `frontend/src/components/SiteHeader.tsx` — ONLY the search trigger (1 import + 1 element)
- `frontend/e2e/search.spec.ts` (new)
- `STATE-SEARCHUI.md` (this file)

## Tickets

| Ticket | Commit | What |
|---|---|---|
| SU1 | `2573f92` | `searchMarkets(q, limit)` typed client for the FROZEN contract `GET /api/v1/search?q=&limit= → {items:[{slug,title,category,icon,volume,yes_price,hours_to_close}], total, query}`. Live-first (ensureApiBase/hasLiveApi), tolerant normalization (accepts envelope or legacy bare array), never rejects on API failure — degrades to a PAPER mock catalog (`terminal-api.ts` pattern). Caller aborts rethrown (stale-request drop). Vitest: 3 new cases (shape / empty q → empty / fallback). `searchUnified` (legacy HeaderSearch client) untouched — additive only. |
| SU2 | `4d54075` | Command palette: `components/search/SearchPalette.tsx` (centered modal over blurred charcoal scrim; framer-motion spring open, instant under `prefers-reduced-motion`; 200ms debounce; every keystroke aborts the previous in-flight request; rows = icon tile, title, mint category chip, hours-to-close, yes_price %, sim volume; ↑/↓ wrap + scroll-into-view; Enter → `/markets/<slug>`; ESC / backdrop close; focus trap, scroll lock, focus restore; idle empty state with shortcut legend; shimmer skeleton; honest no-results; "Paper preview" chip on mock source + paper-trading disclaimer; reserved body/footer heights; mint-on-charcoal tokens, NO danger-red). `SearchCommand.tsx` (magnifier trigger + platform-aware Cmd/Ctrl-K hint, global hotkey). `search-format.ts`, `SearchIcons.tsx`. SiteHeader: trigger mount only. |
| SU3 | `3c4ba3c` | `e2e/search.spec.ts` — 5 DOM-assertion tests: Cmd/Ctrl-K opens (input focused, idle empty state) + ESC closes; typing shows PAPER mock rows after the debounce (canonical Lakers/Celtics title + "Paper preview" chip); arrow keys + Enter → `/markets/nba-2025-01-15-lal-bos`; click row → `/markets/btc-150k-2026-12-31`; nonsense query → no-results with zero rows. Console errors collected via shared helper (network noise filtered; dead-port `Failed to fetch` pageerror documented + filtered in-spec; React crashes strict). |
| hardening | `e9e5b34` | Found during verification: (1) `searchMarkets` live fetch capped at 4s (`SEARCH_LIVE_TIMEOUT_MS`) — a stalled network/proxy could otherwise pin the skeleton forever; caller aborts still rethrow, internal timeout degrades to mock. (2) Trigger gets `relative z-10`: at 1280px the header row overflows its flex budget and the nav's position-relative links paint over the right cluster (PRE-EXISTING layout defect — the links also paint over the HeaderSearch box); the positioned trigger stays clickable without touching layout. (3) Spec: hydration-safe open helpers (retry press/click until React attaches), current onboarding key `ae_onboarded_v1` seeded (shared helper only seeds the legacy key), `waitForURL` at `domcontentloaded`. |

## Decisions & notes for the auditor

- `goals/loop-v79/UI-DIRECTION.md` (named in the work order) **does not exist in this worktree** (`goals/loop-v79/` contains only `STATE.md`). Theme/motion followed from `FRONTEND_DESIGN_SPEC.md` (mint `#20C997` on charcoal, token table) and `frontend/docs/QUESTFLOW_DESIGN_SYSTEM.md` (Motion: keep framer-motion, respect `prefers-reduced-motion`), plus the repo's own `OnboardingTour.tsx` `useReducedMotion` idiom.
- `frontend/src/lib/search-api.ts` already existed with `searchUnified` (consumed by `HeaderSearch.tsx`, which is OUT of charter). SU1 is strictly additive; legacy function byte-identical.
- E2E determinism: the dev server runs with `NEXT_PUBLIC_API_URL` pointing at a dead port, so the live-first fetch fails fast and rows come from the deterministic PAPER mock catalog. (Never read image artifacts — DOM assertions only; playwright screenshots were not opened.)
- "Reserved heights": palette body `h-[340px]` + footer `h-11` are fixed so panel geometry is visreg-stable; header row height (`h-[56px]`) unchanged.
- Dev-server hygiene (per work-order rule): orphan `next dev` processes squatting on :31099 were killed, `.next` cleared once (stale webpack), server restarted clean before the passing run.
- Retry budget: playwright command ran 1 initial + 2 retries (pass on retry 2) — within the 2-retries/command rule. No escalation triggered.
- No push performed.

## Proofs (final, on committed code)

```text
npm run typecheck   → tsc --noEmit, clean (tsconfig includes e2e/**)
npm run lint        → eslint src --max-warnings=0, clean
npm run build       → ✓ Compiled successfully in 60s · ✓ Generating static pages (114/114) · exit 0
npx vitest run src/lib/search-api.test.ts → Test Files 1 passed (1) · Tests 7 passed (7)
E2E_SKIP_WEBSERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:31099 npx playwright test e2e/search.spec.ts --project=chromium
  ok 1 › Cmd/Ctrl-K opens the palette focused on the input; ESC closes it (4.6s)
  ok 2 › typing shows paper mock results after the debounce (4.4s)
  ok 3 › arrow keys navigate and Enter opens the highlighted market (6.0s)
  ok 4 › clicking a result navigates to its market page (4.1s)
  ok 5 › a query with no matches renders the no-results state (3.3s)
  5 passed (24.9s)
```

## Auditor re-run recipe

```bash
cd frontend
npm ci
npm run typecheck && npm run lint
npm run build
npx vitest run src/lib/search-api.test.ts
# terminal B — clean dev server (kill any squatter on :31099; rm -rf .next if webpack stale):
env NEXT_PUBLIC_API_URL=http://127.0.0.1:1 npm run dev -- -p 31099
# terminal A — after HTTP 200 on http://127.0.0.1:31099/:
env E2E_SKIP_WEBSERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:31099 \
  npx playwright test e2e/search.spec.ts --project=chromium
```

AutoLab: not applicable (no iterative measure — feature build verified by the
ticket gate commands; best artifact kept, nothing handed off worse than baseline)
