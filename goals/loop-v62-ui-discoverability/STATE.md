# Loop V62 — UI discoverability redesign · STATE

Worktree: `E:/polymarket-worktrees/loop62-ui` · branch `loop62/ui-discover`
Scope: frontend only. Binding: `GOAL.md` (the 15-second rule) +
`frontend/.claude/CLAUDE.md` (tokens, dark-first, no new UI libraries).

## Ticket status

| Ticket | Status | Evidence |
|---|---|---|
| R1 Information architecture (nav overhaul + `/features` map) | **DONE** | accepted by orchestrator |
| R2 Home hero (15s comprehension, three loops) | **DONE** | see R2 notes + gate below |
| R3 Feature spotlight (coach marks, NEW badges, empty states) | **DONE** | see R3 notes + gate below |
| R4 Motion pass (easing tokens, tickers, chart reveals) | **DONE** | see R4 notes + gate below |
| R5 Discoverability audit table (feature→route→clicks≤2→label) | **DONE** | table below; 0 misses |
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

## R2 — DONE (commit `feat(loop62): R2 …`)

**What shipped**
- **`frontend/src/components/HomeHero.tsx`** — comprehension hero mounted at the
  top of the landing page (`app/page.tsx`), above the discover grid, so it is
  the first thing every visitor sees (heroTop ≈110px, right under the header).
- Honest 15-second copy: kicker "Paper-trading prediction markets", H1 "See the
  edge, trade it on paper, and prove the call.", and a plain-language line —
  "AlphaEdge is a paper-trading simulation … simulated funds only, with no
  real-money execution." No advice language, no fabricated numbers.
- **Three core loops as animated cards**: Predict → `/markets`, Track → `/pods`,
  Prove → `/eval`, each with step number + shared nav icon + honest blurb + CTA.
  Scroll-revealed via existing `MotionReveal` (reduced-motion safe) with a small
  stagger; hover lift guarded by `motion-reduce:transform-none`.
- Two primary CTAs: "Explore markets" → `/markets`, "See everything it does" →
  `/features` (ties the hero back to the R1 map).

**Browser-verified** (dev port 3262, after clearing `.next`): hero present on
`/`, correct title, three loops link to /markets//pods//eval, paper-trading
truth visible, 0 console errors, no horizontal overflow at 1280 or 375 (cards
stack single-column on mobile).

**Gate (R2) — all green**: typecheck 0 · lint 0 · vitest **75 files / 461
tests** (+4 new `HomeHero.test.tsx`) · build 102/102.

Note (encode-once): running `npm run build` while the dev server is up corrupts
the shared `.next` (MODULE_NOT_FOUND ./NNNN.js → 500). Fix: stop preview, `rm
-rf .next`, restart. Verify UI in the browser BEFORE running a production build.

## R3 — DONE (commit `feat(loop62): R3 …`)

**What shipped**
- **Coach marks** (`components/CoachMarks.tsx`, mounted in `layout.tsx`):
  first-visit, dismissable corner card spotlighting the 6 nav groups (from the
  registry) + "Open the feature map →" (`/features`). Storage is a single
  boolean seen flag `alphaedge.coachmarks.v1` — **never auth data** (browser-
  verified: only `coachmarks.v1` + existing `onboarded` keys after dismiss).
  Non-blocking corner placement so it doesn't fight the first-bet modal.
- **NEW badges from the registry**: `feature-registry.ts` `badge:"NEW"` now set
  on Pods + Heartbeat; rendered on `/features` cards (already) and as a NEW pill
  in the More mega-menu. Data-driven, not hardcoded per-item.
- **Honest empty states**: new canonical `components/EmptyState.tsx`
  (title + "what will appear" body + feeder-link CTA), API-compatible with the
  existing per-page local EmptyStates. Adopted in `QuestDiscoverShell` (the bare
  "No markets" text → linked EmptyState → `/markets`). Per-page honest empty
  states already exist on watchlist/alerts/forecast/pods etc. and already link
  to feeders (to be catalogued in the R5 audit).

**Reduced-motion fix (encode-once)**: the first CoachMarks draft used
framer-motion `AnimatePresence` with an empty `exit` under reduced-motion —
`onExitComplete` never fired, so "Got it" set the flag but the card lingered
until reload. Rewrote to a plain conditional mount + CSS `animate-fade-up`
(auto-zeroed by the globals.css reduced-motion kill-switch). Browser-verified:
dismiss now unmounts immediately; card does not reappear after reload.

**Browser-verified** (dev port 3262): coach marks show on first visit (6 groups
+ /features link), dismiss writes only the seen flag and clears instantly, stays
gone after reload; Pods `/features` card shows NEW badge; 0 *current* console
errors (stale HMR syntax errors from a transient mid-edit state were flushed —
module compiles and renders live).

**Parked / unresolved**: could not observe the QuestDiscoverShell EmptyState
*live-empty branch* in the browser — with no local backend the discover shell
stays in the loading (skeleton) state, so `!loading && filtered.length===0`
never triggers. EmptyState itself is unit-tested and its wiring is build-clean.
What-to-check-next: run against a reachable API (or seed initialMarkets) and
search a no-match query to see the linked empty state render.

**Gate (R3) — all green**: typecheck 0 · lint 0 · vitest **77 files / 465
tests** (+4: EmptyState ×2, NEW-badge ×1, CoachMarks ×1) · build 102/102.
Independent verifier: PASS (7/7 guardrails; localStorage seen-flag only,
reduced-motion unmount safe, registry-driven badge, no new deps).

## R4 — DONE (commit `feat(loop62): R4 …`)

**What shipped**
- **Shared motion tokens** (`tailwind.config.ts`): `ease-swift`
  (`cubic-bezier(0.22,1,0.36,1)` — the one canonical easing, previously
  duplicated as a literal in fade-up / slide-in / MotionReveal) +
  `duration-250`. Enter/hover/transition now sit in the 150–250ms band.
- **Adopted `ease-swift`** on the new R1–R3 interactive surfaces: HomeHero loop
  cards, `/features` cards, EmptyState CTA, CoachMarks CTA.
- **Animated number ticker**: new `CountUp.tsx` (reveal-on-view via
  IntersectionObserver, reduced-motion safe) drives the `/features` total
  ("All N capabilities" counts up). Browser-verified reaching 29.

**Existing motion, verified reduced-motion gated (no rework needed)**:
`AnimatedNumber` (17 usages, rAF tween, jumps instantly when reduced),
decision-log blink (`animate-flash-green/red/ticker-in` in DecisionLogTerminal),
scroll/chart reveals (`MotionReveal`, `EdgeHistoryChart`), and the global
`globals.css` `@media (prefers-reduced-motion: reduce)` kill-switch that zeroes
all CSS animation/transition durations.

**Robustness fix (encode-once)**: `CountUp` initially relied on rAF to count
0→N. In a throttled/background tab rAF doesn't advance, leaving the stat stuck
at **0** — a *misleading* number (reads as "0 capabilities"), not just a missing
flourish. Fixed two ways: (1) run immediately when the element is already in the
viewport (don't wait on an IO callback, which also never fired in the headless
preview); (2) a guaranteed `setTimeout(setDisplay(value), duration+120)` so the
true value always lands regardless of rAF. Also dropped framer's
`useReducedMotion` here (its null→false settle re-ran the effect and cancelled
the in-flight count); reduced-motion is read once via `matchMedia`.

**Gate (R4) — all green**: typecheck 0 · lint 0 · vitest **78 files / 467
tests** (+2 CountUp) · build 102/102.

**Tooling note**: the browser MCP console buffer kept replaying stale
`CoachMarks … motion.aside` syntax errors from R3's mid-edit window even after a
full server restart + cache clear + `console.clear()`. They are false positives
— current `CoachMarks.tsx` has no `motion.aside`, and typecheck/lint/build all
pass and the page renders. Trust the CLI gate, not the replayed console buffer.

## R5 — DONE · discoverability audit (commit `feat(loop62): R5 …`)

**Rule**: every feature ≤2 clicks from home (`/`). A "click" counts a link
navigation or a menu-open. Two universal paths make every feature ≤2:
(a) **Feature map** — `/features` is 1 click from home (visible **Features** nav
item on xl; **All features** row in the More menu; **Feature map** in the
footer, present on every page), then the feature card is the 2nd click; and
(b) many features are 1 click directly via the primary nav, the home hero's
Predict/Track/Prove cards, the header bells, or the footer.

Verified against the shipped nav/registry (`SiteHeader`, `HeaderMoreMenu`,
`HomeHero`, footer in `layout.tsx`, `feature-registry.ts`). **0 misses** — no
feature exceeds 2 clicks.

| Feature | Route | Clicks | Best visible label / surface | ≤2 |
|---|---|---|---|---|
| Discover (home) | `/` | 0 | Nav "Discover" (active on home) | ✅ |
| Markets | `/markets` | 1 | Nav "Markets"; hero "Explore markets"; footer "Markets" | ✅ |
| Trade | `/trade` | 1 | Nav "Trade" | ✅ |
| Signals | `/signals` | 1 | Nav "Signals" (unread badge) | ✅ |
| Portfolio | `/portfolio` | 1 | Nav "Portfolio" + header Portfolio button | ✅ |
| Eval (proof) | `/eval` | 1 | Home hero "Prove" card; footer "Proof" | ✅ |
| Pods | `/pods` | 1 | Home hero "Track" card; footer "Pods"; `NEW` | ✅ |
| Heartbeat decisions | `/pods` (embedded) | 1 | Inside Pods (hero "Track" card); `NEW` | ✅ |
| Alerts | `/alerts` | 1 | Header AlertsBell → `/alerts` | ✅ |
| Notifications | `/alerts` (bell overlay) | 1 | Header NotificationBell | ✅ |
| Home (desk) | `/home` | 1 (xl) / 2 | Nav "Home" (xl); else More/Features | ✅ |
| Clones | `/clones` | 1 (xl) / 2 | Nav "Clones" (xl); else More/Features | ✅ |
| Features map | `/features` | 1 | Nav "Features" (xl); More "All features"; footer | ✅ |
| Market context panel | `/markets` (embedded) | 2 | Open a market (Markets→market) | ✅ |
| AI Analyze | `/markets` (overlay) | 2 | ✦ AI Analyze button on a market | ✅ |
| Opportunities | `/opportunities` | 2 | Features card / More "Opportunities" | ✅ |
| Compare | `/compare` | 2 | Features card / More "Compare" | ✅ |
| Arb | `/arb` | 2 | Features card / More "Arb" | ✅ |
| Research | `/research` | 2 | Features card / More "Research" | ✅ |
| Forecast | `/forecast` | 2 | Features card / More "Forecast" | ✅ |
| Smart money | `/smart-money` | 2 | Features card / More "Smart money" | ✅ |
| Backtest | `/backtest` | 2 | Features card / More "Backtest" | ✅ |
| Weather | `/weather` | 2 | Features card / More "Weather" | ✅ |
| Macro | `/macro` | 2 | Features card / More "Macro" | ✅ |
| Track record | `/track-record` | 2 | Features card / More "Track record" | ✅ |
| Resolved | `/resolved` | 2 | Features card / More "Resolved" | ✅ |
| Feed | `/feed` | 2 | Features card / More "Feed" | ✅ |
| Traders & leaderboard | `/leaderboard` | 2 | Features card / More "Traders & leaderboard" | ✅ |
| Watchlist | `/watchlist` | 2 | Features card / More "Watchlist" | ✅ |
| System status | `/admin/observability` | 2 | Features card (auth); header health chip | ✅ |
| Admin | `/admin` | 2 | Features card (auth-gated) | ✅ |

Notes: "1 (xl) / 2" items (Home, Clones, Features) collapse into the More menu
below the xl breakpoint but stay ≤2 there (More-open + item, or the always-
present footer "Feature map"). Auth-gated surfaces (System status, Admin) are
discoverable at ≤2 clicks; the pages themselves still require sign-in — that is
honest gating, not a discoverability miss.

## Guardrails honored
No new UI libraries (icons are hand-written SVG). No order/trade mutation logic
touched. No fabricated data/metrics; empty/embedded surfaces stated honestly.
Paper-trading truth kept visible. Not pushed, not merged.

## AutoLab
AutoLab: baseline=frontend gate green (typecheck/lint/vitest 457/build) |
benchmark=gate green + /features discoverability (all features ≤2 clicks, 0
console errors) | iterations=1 (R1 landed first pass; fixed TS JSX-namespace +
lint no-html-link + test HTML-escape) | budget=1/6 tickets | outcome=improved

AutoLab: baseline=R1 gate green (vitest 457) | benchmark=home hero 15s
comprehension (paper-trading truth + 3 loops deep-linked, 0 console errors, no
overflow 1280/375) | iterations=1 (landed first pass; recovered dev server via
.next clear after build clobber) | budget=2/6 tickets | outcome=improved
(vitest 457→461)

AutoLab: baseline=R2 gate green (vitest 461) | benchmark=feature-spotlight
(coach marks first-visit + dismiss-persist, NEW badge from registry, honest
linked empty state) | iterations=2 (draft framer-motion coach marks hung under
reduced-motion → rewrote to CSS-animated plain mount; re-verified dismiss
unmounts instantly) | budget=3/6 tickets | outcome=improved (vitest 461→465)

AutoLab: baseline=R3 gate green (vitest 465) | benchmark=motion pass (shared
ease-swift/duration tokens, CountUp ticker reaches true value, existing
tickers/blink/reveals reduced-motion gated) | iterations=2 (CountUp stuck at 0
under rAF throttle + framer useReducedMotion re-run bug → matchMedia + in-view
immediate-run + guaranteed settle timeout) | budget=4/6 tickets |
outcome=improved (vitest 465→467)

AutoLab: not applicable (R5 is a discoverability audit doc — no iterative
measure). Result: 31 rows audited, every feature ≤2 clicks from home, 0 misses,
so no code fix required.
