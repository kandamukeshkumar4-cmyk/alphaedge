# AlphaEdge × QuestFlow App Design System

> **North star (2026-07):** the QuestFlow agentic-trading app (`next.questflow.ai`)
> — a dark terminal-style trading product with a flat product-level tab row,
> a unified portfolio view, AI insight panels on every market, and
> copy-trading surfaces. This document records the design system derived from
> it and how AlphaEdge maps onto it. It supersedes the visual-shell portions
> of `FRONTEND_DESIGN_SPEC.md` (the Kalshi × Polymarket layout guidance there
> still applies to page structure).

## Provenance (v2 — real screenshots)

**2026-07 update:** the owner supplied 9 screenshots of the live
`next.questflow.ai` app; the token set and component anatomy below were
re-extracted from them directly (v1 values were derived from written
descriptions and are superseded). Verified elements: green-tinted
near-black canvas, teal/mint brand, cents pricing in teal, per-outcome
rows with tinted Yes/No buttons, outlined "AI Analyze" card CTA,
TradingView-classic candles (#26A69A/#EF5350) with volume bars and a teal
last-price axis chip, LONG/SHORT signal badges, red→orange rank numbers,
platform chips, wallet pill + filled-teal deposit button, and a 3-item
bottom nav (Feed | Discover | Chat → mapped to Feed | Discover |
Portfolio). Branding, assets, and copy remain AlphaEdge's own.

## Provenance & honesty note (v1, superseded)

`questflow.ai` / `next.questflow.ai` are not reachable from the CI/agent
environment (network policy), so this system was **derived from published
descriptions** of the product — the Questflow blog (One AI Clone, Every
Market; Hyperliquid integration; prediction markets + perps convergence) and
third-party guides describing the app's navigation and screens — plus the
established visual language of dark agentic-trading terminals. Token hexes
are our own original values tuned to that aesthetic, not extracted from
QuestFlow assets. If someone with browser access captures exact brand values
later, retune `tailwind.config.ts` + `src/app/globals.css` (single source of
truth) and every tab reskins automatically.

## Structure mapping (QuestFlow app → AlphaEdge)

| QuestFlow app | AlphaEdge route | Notes |
|---|---|---|
| Feed | `/` | Curated opportunities feed (hero + discovery rail) |
| Trade / Markets | `/markets`, `/markets/[slug]` | Market grid + detail with chart, order book, trade panel |
| AI insights / Smart Clone | `/signals`, `/forecast` | AI signals + model forecasts on every market |
| Copy trade | `/mirror` | Mirror top traders (paper simulation) |
| Leaderboard (Trader Arena) | `/leaderboard` | Human + AI performance ranking |
| Unified portfolio (GDP-style stats) | `/portfolio` + header balance chip | One balance across all market types |

Top nav matches the QuestFlow video — **Discover | Trade | Leaderboard |
Markets | Signals | GDP** — with a neon-teal glowing underline on the active
tab (see `SiteHeader.tsx`). Discover (`/`) hosts Markets/Feed sub-tabs; Trade
(`/trade`) is the chart + order book + reports terminal; GDP maps to
`/portfolio`. Persistent **ATLAS** right rail is the AI placement surface.

## Color tokens (dark-only terminal)

Defined in `tailwind.config.ts` and mirrored as `!important` utilities in
`src/app/globals.css`.

| Token | Hex | Use |
|---|---|---|
| `bg` | `#0C1210` | Green-tinted near-black canvas |
| `surface` / `surface-2` / `surface-3` | `#0C0E12` / `#12151B` / `#1A1E26` | Cards → raised → hover |
| `border` / `border-light` | `#1D222C` / `#2C323E` | Hairline dividers |
| `text` / `muted` / `muted-2` | `#F2F4F8` / `#97A0B2` / `#5E6779` | Text hierarchy |
| `primary` / `up` | `#2DD4BF` | Brand teal — prices, YES, active, gains |
| `primary-dim` | `#04281B` | Green tint surfaces |
| `danger` / `down` | `#F1585C` | NO, losses; chart candles use #EF5350 |
| `accent` | `#14B8A6` | Deep teal — filled CTAs (deposit, hero trade) |
| `secondary` | `#22D3EE` | Cyan — informational secondary accents |
| `gold` | `#F6C244` | Leaderboard / trophies |

Semantics: **green/red are reserved for trade direction**; violet marks
anything AI/agent-driven; cyan is informational. Charts
(`PriceChart`, `MultiLineChart`, `Sparkline`, `OrderbookDepthChart`,
`ProbabilityHistoryChart`) use the same hexes.

Typography: Inter (UI) + IBM Plex Mono (all numerals, prices, balances),
`tabular-nums` for live values.

## Astryx (Meta design system)

Astryx (`@astryxdesign/core` + `@astryxdesign/theme-neutral`) is installed
and provides accessible primitives, re-branded to this palette:

- **Setup:** `src/app/layout.tsx` imports `reset.css`, `astryx.css`,
  `theme.css`; `src/app/providers.tsx` wraps the app in
  `<Theme theme={neutralTheme} mode="dark">` + `LinkProvider` (next/link).
- **Branding:** token overrides live in `globals.css` under
  `[data-astryx-theme]` (accent → violet, success → signal green, surfaces →
  terminal blacks, fonts → Inter/Plex Mono).
- **In use today:** `Button` (header auth actions), `TabList`/`Tab` +
  `Badge` (market detail tabs, YES/NO chips in Activity/Holders).
- **Discover more:** `node node_modules/@astryxdesign/core/docs.mjs --list`
  or `npx astryx component <Name>`; templates via `npx astryx template --list`.

Prefer an Astryx primitive over a hand-rolled one when touching a component;
keep bespoke market-specific composites (charts, order book, trade panel) as
Tailwind components using the tokens above.

## Design kit (`src/components/ui/kit.tsx`)

Every tab is composed from one shared primitive set so the app reads as a
single product — retune tokens, not these:

- `PageShell` / `PageHeader` — consistent max-width + kicker/title/subtitle/actions header on every route.
- `SectionHeader` — section title + optional action link.
- `Panel` — bordered surface card with optional header row.
- `StatTile` / `StatRow` — the QuestFlow stat strips (mono numerals, tone-colored deltas, accent variant).
- `AiEdge` — the violet "AI edge +8%" badge shown on every market card.
- `SegTabs` — segmented control (Standings sort, market status).
- `Chip` — category filter pills.

### Per-tab rebuilds (not just recolor)

| Tab | What was rebuilt |
|---|---|
| Feed (`/`) | Hero + **stat strip** (live markets / 24h vol / traders / AI signals) + AI-edge market cards + discovery rails |
| Markets (`/markets`) | Stat strip, category chips, status `SegTabs`, big-% AI-edge card grid, demo fallback so it renders without an API |
| Leaderboard (`/leaderboard`) | Full **Trader Arena**: arena summary tiles, top-3 **podium**, sortable `SegTabs` standings, per-row **Copy** (mirror) CTA, demo fallback |
| Signals (`/signals`) | Kit header + paper-P&L panel + signal feed / CLV track record |
| Forecast · Mirror (`/forecast`, `/mirror`) | Smart-Clone kicker, stat tiles, calibration / track-record / trend panels |
| Portfolio (`/portfolio`) | Unified-portfolio kit header (auth-gated) |
| Market detail (`/markets/[slug]`) | Decision-stack side panel, animated chart, Astryx tabs + YES/NO badges |

Cards carry a deterministic demo **AI edge** so the grid feels model-driven
without a live call; it is clearly a demo signal, not a real forecast.

## Motion

Existing framer-motion + CSS keyframes stay: `fade-up` reveals,
`flash-green`/`flash-red` on live price ticks, soft pulse on live dots.
Respect `prefers-reduced-motion` (already global).

## Guardrails

The reskin is visual only. Paper-trading disclaimers, the `Sim` badge in the
header, and all `PAPER_TRADING_ONLY` copy must remain visible. No cash/
funding language may be introduced by design changes.
