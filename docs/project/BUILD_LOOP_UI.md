# BUILD_LOOP_UI — PolyScout frontend (Kalshi mirror × Coinbase design system)

Two-agent adversarial build loop. Same maker/checker protocol that shipped the
backend (14/14 tickets, gate 669p/5s):

- **Loop A (maker): Opus 4.8** — claims a ticket, writes a first-principles design
  note in the ticket file, implements, runs an adversarial break pass, runs the
  gate, flips the ticket IN-REVIEW.
- **Loop B (checker): Cursor Composer 2.5** — re-runs the gate, reviews the diff
  against THIS spec (not its own interpretation — but if Opus under-builds vs this
  spec, FAIL it with concrete findings), verdict PASS→DONE or FAIL→CLAIMED-OPUS
  with findings in STATE.md.

Coordination spine: `goals/ui-loop/STATE.md` (queue table + decisions log), one
ticket file per claim at `goals/ui-loop/U{nn}.md`. Shared working tree — handoff
via STATE.md, no cross-committing of the other agent's in-flight work.

---

## §1 Mission

Rebuild the AlphaEdge frontend as an **exact structural mirror of kalshi.com**
skinned entirely with the **Coinbase design system** (`docs/design/DESIGN-coinbase.md`),
consuming the live backend — markets/candles/WS from the existing API plus the T12
PolyScout contract (brief feed, track record, graded claims, latency badges).

Two non-negotiable pillars:

1. **STRUCTURE = KALSHI, EXACTLY.** Every surface, grid, and placement a visitor
   sees on kalshi.com must exist here in the same position: the nav layout, the
   category tab bar, the featured row, the market-card grid geometry, the event
   detail split (chart left / trade panel right), the tab order, the footer. If
   Kalshi shows it, we show it, in the same place. Deviations are FAIL findings.
2. **SKIN = COINBASE, EXCLUSIVELY.** Every color, radius, font, spacing, and
   component treatment comes from `docs/design/DESIGN-coinbase.md` tokens. No
   inline hex anywhere — tokens only, wired through Tailwind theme. Kalshi's own
   teal/green branding must NOT leak in; the only green/red are
   `semantic-up`/`semantic-down` as **text color only, never backgrounds**
   (design-doc "Don't" list is binding).

Font substitutes (design doc §Note): CoinbaseDisplay/Sans → **Inter** (400/600),
CoinbaseMono → **JetBrains Mono** 500 on every number.

## §2 Guardrails (non-negotiable — same as backend)

- Paper-trading simulation ONLY. All trade UI copy says paper/simulated. No cash
  funding, deposit, withdrawal, or payment language anywhere.
- The trade panel calls the existing paper-order API only. No new order paths; the
  frontend never bypasses RiskService semantics (backend enforces; frontend must
  not pretend otherwise).
- Design tokens only — never inline hex, never a second brand color, never bold
  display type (weight 400 per design doc), never green/red button backgrounds.
- Do not delete working pages/components until their replacement passes the gate.
- Never weaken the gate to pass a ticket.

## §3 Verification gate (run from `frontend/`)

```
npm run lint && npm run typecheck && npm run build && npx vitest run
```

All four must be green before IN-REVIEW. Cursor re-runs the same gate on verify.
Each ticket also has a **Kalshi-mirror acceptance checklist** (below) that Cursor
verifies visually via the dev server (`npm run dev`) or preview tooling.

Backend for local dev: `cd backend && uv run uvicorn app.main:app` (T12 endpoints:
`GET /api/v1/briefs`, `/briefs/{id}`, `/analyst/track-record`,
`/analyst/track-record/claims`, `/markets/{slug}/latency`; existing:
`/markets`, `/markets/{slug}/candles|history|latest`, `WS /api/v1/ws/prices`).
Every data-driven component must also render correctly with the backend DOWN
(skeleton → graceful empty state, never a crash) — this is a standing accept
criterion on every ticket.

## §4 Ticket queue

Dependency rule: U01 blocks everything; U02–U03 block U04+; otherwise claim in
order. Copy the spec section into `goals/ui-loop/U{nn}.md` on claim.

### U00 — Ticket Zero: baseline
Run the full gate on the untouched tree; record the baseline result in STATE.md.
If red, fix ONLY what makes it green. Accept: gate green, baseline recorded.

### U01 — Design token foundation
Translate `docs/design/DESIGN-coinbase.md` YAML into `tailwind.config.ts` theme
extensions + CSS variables in `globals.css`: all colors, typography scale (Inter +
JetBrains Mono via `next/font`), radius scale (xs 4 → xl 24, pill 100, full),
spacing tokens (incl. `section: 96px`), the single shadow tier
(`0 4px 12px rgba(0,0,0,0.04)`). Ship a `/design` dev-only page rendering every
token + component primitive (buttons primary/secondary/outline-dark/tertiary,
badge-pill, search-input-pill, text-input, asset-icon plate) for visual review.
Accept: gate green; `/design` shows every token; grep proves zero new inline hex
in components; number values render in mono.

### U02 — Top nav + category bar (Kalshi mirror)
Kalshi's two-tier header, Coinbase-skinned:
- Tier 1 (64px, `top-nav-light`): wordmark left; pill search bar center
  (`search-input-pill`); right cluster: watchlist star, notifications, portfolio
  balance chip (paper), avatar/sign-in (`button-primary` pill).
- Tier 2: horizontal scrollable category tab bar exactly as Kalshi orders it —
  **Live/New · Politics · Sports · Culture · Crypto · Climate · Economics ·
  Companies · Financials · Tech & Science · Health · World** — active tab ink
  underline, inactive `muted`. Categories filter the markets grid via URL param.
- Below 768px: hamburger sheet, search collapses to icon; primary CTA stays.
Accept: gate green; both tiers pixel-match Kalshi's placement; tab click filters
grid; keyboard navigable; zero non-token colors.

### U03 — Home page: featured row + market grid + live ticker (Kalshi mirror)
Kalshi's home structure, same order top-to-bottom:
1. Featured/trending cards row (horizontal scroll, large image cards) —
   `product-ui-card-light` treatment, hairline border, 24px radius.
2. Category section rails ("Trending", per-category rows) with "See all" links.
3. Main market-card grid: responsive 4-col desktop / 2-col tablet / 1-col mobile,
   24px gutters, cards sorted by volume.
4. A slim live-activity ticker strip (recent price moves via WS) — Kalshi shows
   live activity; ours streams from `WS /api/v1/ws/prices` + signal events.
Accept: gate green; section order matches Kalshi; grid breakpoints per design-doc
responsive table; live ticker updates without refresh; skeleton loading states.

### U04 — Market card (the atom, Kalshi mirror)
Kalshi's card anatomy exactly: market image (circular plate, `asset-icon-circular`
enlarged), title (title-md), live Yes % as the dominant number
(`number-display` mono), **Yes/No quick-buy buttons side-by-side** (Coinbase
skin: `surface-strong` pills, semantic up/down TEXT color for the % inside — never
green/red fills), volume + close-date caption row, watchlist star top-right,
sparkline of recent history. Multi-outcome markets render Kalshi's stacked-rows
variant (top 3 outcomes + "+N more"). Card click → detail; Yes/No click → detail
with trade panel pre-armed to that side.
Accept: gate green; anatomy checklist above all present; % updates live over WS;
unit tests for the price/format helpers; both variants (binary + multi) render.

### U05 — Market detail page (Kalshi mirror: chart left, trade right)
Kalshi's event-page split:
- **Left column:** breadcrumb (category / event); title block with image; big
  live % + change; price chart with Kalshi's timeframe selector row
  (1H · 6H · 1D · 1W · 1M · ALL) fed by candles/history APIs; below the chart the
  Kalshi tab strip — **About/Rules · Activity · Comments-placeholder** — plus our
  **Research** tab (T12 briefs for this market, U06 component reuse).
- **Right column (sticky):** the trade panel — Yes/No toggle, price display,
  quantity stepper, cost/payout math, `button-primary` pill submit → existing
  paper-order API, position summary if held. Header carries an explicit
  "Paper trading — simulated funds" `badge-pill`.
- Bottom: related-markets rail (same event/category).
Accept: gate green; two-column split + sticky panel matches Kalshi; timeframes
switch data; paper order placed end-to-end against local backend; rules/activity
tabs populated; mobile collapses to Kalshi's order (chart → trade CTA bar pinned
bottom → tabs).

### U06 — Research briefs surface (T12 contract)
The differentiator Kalshi doesn't have — presented in Kalshi's idiom:
- `/research` page: paginated brief feed (`GET /briefs`, filters market/category/
  kind) rendered as feature-cards; each shows headline, market chip, generator
  badge (llm/fallback), created time, and the claim as a `badge-pill`
  (direction + horizon + status color = semantic text).
- Brief detail (`/research/[id]`): body markdown, **citations list** (every brief
  has ≥1), claim card with grade once resolved (correct/incorrect/void), link to
  its market.
- Market-detail Research tab (U05) reuses the feed component filtered to slug.
Accept: gate green; feed paginates + filters; detail renders citations + claim
verdict states; empty state when no briefs; component tests for claim-badge
state mapping.

### U07 — Track record + graded claims (the public eval surface)
`/track-record` page consuming `GET /analyst/track-record` + `/claims`:
- Headline scoreboard: accuracy + Brier, 7d/30d/all windows, `provisional`
  badge when n<30 (never hide n).
- Breakdown tables by category, claim-type, model_version, prompt_version —
  `asset-row` treatment, numbers in mono, up/down semantic text.
- Graded-claims feed: every claim with verdict — **the misses render as
  prominently as the wins** (transparency is the product; hiding losses = FAIL).
Accept: gate green; all aggregate dimensions rendered; provisional flag visible;
claims feed paginates; numbers mono; no green/red backgrounds.

### U08 — Live wiring: WS prices + latency badges
- One shared WS client (reconnect w/ backoff, tab-visibility pause) feeding
  cards, detail header, and ticker; prices flash via subtle text transition
  (semantic color), never layout shift.
- Latency/freshness badge (`GET /markets/{slug}/latency`) on detail header +
  cards: Live (<60s) / Delayed / Stale states as `badge-pill`.
Accept: gate green; two tabs stay in sync; kill backend → UI degrades to Stale
badges without crash; reconnect proven; unit tests for the badge state machine.

### U09 — Portfolio + watchlist (Kalshi mirror)
Kalshi's portfolio layout: balance header (paper balance, prominent mono),
positions table (market, side, qty, avg cost, current, unrealized PnL in semantic
text), open orders, settled history tab; watchlist page fed by the starred
markets (localStorage + existing API where available). "Paper" badge on every
money figure.
Accept: gate green; positions reflect placed paper orders end-to-end; PnL math
matches backend; watchlist star round-trips from cards/detail.

### U10 — Search, category pages, footer (Kalshi mirror)
- Search overlay (Kalshi's modal pattern): debounced, grouped results
  (Markets / Events / Research), keyboard navigation.
- `/markets/category/[tag]` pages = the grid filtered, with the category hero
  strip Kalshi shows.
- Footer: Coinbase `footer-light` 6-column link list + `legal-band` with the
  paper-trading disclaimer.
Accept: gate green; search returns and routes; category pages linked from tab
bar; footer on every page.

### U11 — Responsive + polish + a11y pass
Design-doc responsive table enforced across all pages (hero type step-downs,
grid 4→2→1, nav hamburger <768px, detail-page mobile order, pinned trade CTA).
Loading skeletons everywhere data loads; error boundaries; focus states (2px
primary border per design doc); WCAG AA contrast; `prefers-reduced-motion`
respected. Lighthouse (local) ≥90 accessibility.
Accept: gate green; checklist per page recorded in ticket file with screenshots;
Cursor spot-verifies at 375px / 768px / 1280px.

### U12 — Final review (§6 analog)
Whole-app coherence pass: every Kalshi surface present (checklist in §5), zero
inline hex (grep), zero non-token font sizes, guardrail copy audit (no real-money
language), dead-code sweep of replaced legacy components (delete only what nothing
imports), docs update (`explorer-notes.md` + STATE.md completion banner).
Accept: gate green; §5 checklist 100%; STATE.md banner written.

## §5 Kalshi-mirror master checklist (Cursor verifies at U12)

Top nav 2-tier ✓ · category tab bar (12 tabs, correct order) ✓ · pill search ✓ ·
featured cards row ✓ · category rails + "see all" ✓ · market grid 4/2/1 ✓ ·
card: image/title/%/Yes-No buttons/volume/star/sparkline ✓ · multi-outcome card ✓ ·
detail: breadcrumb/chart+timeframes/tabs/sticky trade panel/related rail ✓ ·
portfolio: balance/positions/orders/history ✓ · watchlist ✓ · search overlay ✓ ·
live ticker ✓ · footer + legal band ✓ · mobile pinned trade CTA ✓
— all skinned 100% from DESIGN-coinbase.md tokens.

## §6 AutoLab note

UI tickets are mostly one-shot (no iterative measure) → record
"AutoLab: not applicable" per ticket. Exceptions: U11 uses Lighthouse
accessibility/performance as the benchmark (baseline → iterate → keep best);
record a real AutoLab line there.

## §7 Process rules (identical to backend loop)

1. Claim in STATE.md before touching code; write the design note in U{nn}.md
   BEFORE implementing.
2. Adversarial break pass before IN-REVIEW; record findings in the ticket file.
3. Cursor findings are addressed before DONE — arbitrate against THIS spec, and
   if the spec supports Cursor, rebuild without arguing.
4. Never flip your own ticket to DONE. Never weaken the gate.
5. Truth-first: deviations from spec (or from Kalshi's structure where it
   genuinely can't apply) are flagged explicitly in STATE.md for Cursor, with
   reasoning — silent deviation is a FAIL.
