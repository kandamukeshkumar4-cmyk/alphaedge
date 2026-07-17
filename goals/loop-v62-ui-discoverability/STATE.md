# Loop V62 — UI discoverability redesign · STATE

Worktree: `E:/polymarket-worktrees/loop62-ui` · branch `loop62/ui-discover`
Scope: frontend only. Binding: `GOAL.md` (the 15-second rule) +
`frontend/.claude/CLAUDE.md` (tokens, dark-first, no new UI libraries).

## Ticket status

| Ticket | Status | Evidence |
|---|---|---|
| R1 Information architecture (nav overhaul + `/features` map) | **DONE** | see R1 notes + gate below |
| R2 Home hero (15s comprehension, three loops) | TODO | |
| R3 Feature spotlight (coach marks, NEW badges, empty states) | TODO | registry seeds `badge:"NEW"` already |
| R4 Motion pass (easing tokens, tickers, chart reveals) | TODO | |
| R5 Discoverability audit table (feature→route→clicks≤2→label) | TODO | scaffold below; fill after R2/R3 |
| R6 Gate (typecheck, lint, vitest, build) | PARTIAL | full gate already green as of R1 |

## R1 — DONE (commit `feat(loop62): R1 …`)

**What shipped**
- **Single source of truth**: `frontend/src/lib/feature-registry.ts` — every
  shipped capability listed once, grouped into 6 groups (Markets & trading,
  Intelligence & AI, Proof & track record, People & social, Your account,
  System) with a one-line honest blurb + real deep link. Embedded/overlay/admin
  surfaces carry a `note` saying where they actually live (e.g. AI Analyze =
  overlay from a market; Heartbeat = inside Pods; System status = Admin
  observability). `badge:"NEW"` field seeds R3.
- **`/features` map page**: `frontend/src/app/features/page.tsx` — renders the
  whole registry as grouped cards (icon + title + blurb + deep link + surface
  badge), scroll-revealed via existing `MotionReveal` (reduced-motion safe).
  Prerenders static (○, 485 B). Honest paper-trading copy in the subtitle.
- **Global nav overhaul** (`SiteHeader.tsx`): primary nav is now icon+text (no
  icon-only mystery meat) via shared inline-SVG set `components/nav-icons.tsx`
  (NO new icon library — guardrail honored). Added a visible **Features** item.
  Home/Clones/Features defer to `xl` to keep the 1280 row tight; all stay ≤1
  click via the More map.
- **Grouped "More" mega-menu** (`HeaderMoreMenu.tsx`): rebuilt from the registry
  — 6 labeled groups + a pinned **"All features →"** link to `/features`.
  Replaces the old flat `MORE_NAV` list.
- **Mobile parity**: hamburger menu now renders icon+text primary items, the
  "All features" link, and the full grouped map. Bottom nav unchanged.
- **Footer**: added a labeled quick-nav row (Feature map · Markets · Proof ·
  Pods · Portfolio) so `/features` is reachable from every page without opening
  a menu.

**Browser-verified (dev server port 3262, `loop62-ui` launch config)**
- `/features` renders all 6 groups / 29 features, correct deep links + surface
  badges + honest notes; 0 console errors; title `Features — AlphaEdge`.
- More menu opens: `aria-expanded=true`, 6 group headings, 30 links (29 +
  "All features"), `/features` present.
- No horizontal overflow at 1280 (scrollWidth 1270) or 1024 (1014); at 1024
  primary nav = Discover/Trade/Markets/Signals/Portfolio (Home/Clones/Features
  deferred to xl, still in More).
- Mobile 375: no overflow; hamburger shows All-features link + 6 groups; bottom
  nav = Discover/Trade/Portfolio.

## Gate (as of R1) — all green

- `npm run typecheck` → clean (0 errors)
- `npm run lint` → clean (0 errors, 0 warnings)
- `npx vitest run` → **74 files, 457 tests passed** (incl. new
  `src/app/features/page.test.tsx`, 5 tests)
- `npm run build` → compiled OK, 102/102 static pages, `/features` static
- Pre-existing `quest/` failures: **none exist** in this worktree (explorer +
  full suite confirm). Nothing skipped.

## R5 discoverability audit (scaffold — to complete with R5)

Clicks-from-home rule: every feature must be ≤2 clicks from `/`. With the
`/features` map (1 click from home via nav/footer) + every card being 1 click,
all features are structurally ≤2 clicks. Fill the exact table during R5:

| Feature | Route | Clicks from home | Visible label | OK? |
|---|---|---|---|---|
| _(populate in R5 from feature-registry + real nav paths)_ | | | | |

## Guardrails honored
No new UI libraries (icons are hand-written SVG). No order/trade mutation logic
touched. No fabricated data/metrics; empty/embedded surfaces stated honestly.
Paper-trading truth kept visible. Not pushed, not merged.

## AutoLab
AutoLab: baseline=frontend gate green (typecheck/lint/vitest 457/build) |
benchmark=gate green + /features discoverability (all features ≤2 clicks, 0
console errors) | iterations=1 (R1 landed first pass; fixed TS JSX-namespace +
lint no-html-link + test HTML-escape) | budget=1/6 tickets | outcome=improved
