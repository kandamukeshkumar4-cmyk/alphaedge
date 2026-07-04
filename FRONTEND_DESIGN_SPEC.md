# AlphaEdge Frontend Design Specification
### Best of Kalshi (market grid + odds + rankings) × Polymarket (clean trading + animated charts)

> **Update 2026-07:** the visual shell (palette, nav model, component
> primitives) now follows the QuestFlow-app-inspired terminal system in
> `frontend/docs/QUESTFLOW_DESIGN_SYSTEM.md`, built on Astryx
> (`@astryxdesign/core`). The layout/structure guidance below (grids, rails,
> trading panel anatomy) still applies.

> **North star:** Kalshi's *information density and discovery* (category-organized grid, multiplier odds, ranked sidebars) fused with Polymarket's *trading clarity and motion* (big percentage pricing, prominent live chart, order book, holders/comments). Plus our own edge: **AI predictions visible on every market.**

---

## 0. Reference Breakdown — what we take from each

| Element | Kalshi gives us | Polymarket gives us | AlphaEdge final |
|---|---|---|---|
| **Home layout** | 3-col: nav tabs + category grid + ranked right rail | Clean card feed, big % | Category grid (center) + ranked right rail + featured hero |
| **Market card** | Multi-outcome rows, `3.52x` multiplier + `27%`, volume, market count | Single bold % YES/NO, volume | Multi-outcome rows **with both** `1.85x` odds and `52%` + **AI badge** |
| **Pricing display** | Multiplier (`3.52x`) | Cents/percent (`65¢` / `65%`) | Show **% as primary**, multiplier as secondary on hover |
| **Chart** | Small, static, multi-line (looks weak) | Large, smooth area chart | **Large animated candlestick + area toggle, live-updating** |
| **Trading** | Quick-buy chips | Full BUY/SELL with shares + cost | Polymarket-style panel, sticky |
| **Social** | Trending / Top movers / Highest volume rails | Holders, Comments, Activity | Both: ranked rails + holders + live activity feed |
| **Identity** | "Verify identity" progress, Sign up | Wallet connect | Email signup + "$100k paper" progress bar |

---

## 1. Color Palette (dark-first, Kalshi-green primary)

| Token | Use | Hex |
|---|---|---|
| `primary` | Buy / YES / positive | `#00E676` (Kalshi-style neon green) |
| `danger` | Sell / NO / negative | `#FF4D4F` |
| `accent` | Hover / links / focus | `#00D9FF` cyan |
| `up` / `down` | Chart candles | `#26A69A` / `#EF5350` |
| `bg` | App background | `#0B0E14` |
| `surface` | Cards | `#12161F` |
| `surface-2` | Raised / hover | `#181D29` |
| `border` | Dividers | `#1F2533` |
| `text` | Primary text | `#F5F7FA` |
| `muted` | Secondary text | `#8A93A6` |
| `gold` | Trophy / leaderboard | `#FFC107` |

Typography: **Inter** (UI), **IBM Plex Mono** (prices/odds/numbers). Sizes 12/14/16/18/24/32.

---

## 2. Global Header (Kalshi-style top bar)

```
[AlphaEdge logo]   MARKETS  SPORTS  ELECTIONS  CRYPTO  CULTURE  MORE▾
                   [🔍 Trade on anything........................]   [🏆][🔔]  [Sign up]/[Avatar▾]
─────────────────────────────────────────────────────────────────────────
Trending · Elections · Politics · Sports · Culture · Crypto · Commodities · Economics · Tech
```
- Sticky, dark, thin bottom border.
- Active category underlined in `primary` green.
- Search is prominent and centered (Polymarket + Kalshi both lead with it).

---

## 3. HOME / MARKETS (the main page) — 3-column

```
┌── CENTER (≈60%) ──────────────────────────────┐  ┌── RIGHT RAIL (≈25%) ──┐
│ [FEATURED HERO CARD]                          │  │  Trending          ▸  │
│  CULTURE · Love Island S8E1     ‹ 6 of 7 ›    │  │  1 LA Mayor      66%▲4 │
│  Multi-outcome list + ANIMATED chart on right │  │  2 2028 Dem nom  23%   │
│  ▸ Gabriel 3.52x  27%    [live area chart]    │  │  3 BTC Fri 5pm   42%▼44│
│  ▸ Aniya   23.4x   5%                          │  ├───────────────────────┤
│  $43,672 vol · 9 markets                       │  │  Top movers        ▸  │
├───────────────────────────────────────────────┤  │  1 Vegas vs CAR  89%▲88│
│ [GET READY TO TRADE]                           │  │  2 Goal Leader    1%▼96│
│  Claim your $100,000 paper balance ▓▓▓░ 2/4    │  ├───────────────────────┤
│  [Complete sign up]                            │  │  Highest volume    ▸  │
├───────────────────────────────────────────────┤  │  1 NY vs SA  $246M     │
│  Sports ▸                                      │  │  2 2028 nom  $119M     │
│  ┌───────────────┐ ┌───────────────┐           │  │  3 World Cup $63M      │
│  │ MARKET CARD   │ │ MARKET CARD   │           │  ├───────────────────────┤
│  └───────────────┘ └───────────────┘           │  │  New               ▸  │
│  Pro Baseball ▸                                │  │  ...                   │
│  ┌───────────────┐ ┌───────────────┐           │  └───────────────────────┘
│  │ ...           │ │ ...           │           │
└───────────────────────────────────────────────┘
```
- **Left** is optional on desktop (filters can collapse into the category bar). On wide screens we can add a slim left filter rail; on standard screens use the 2-rail layout above (matches your Kalshi screenshot exactly).
- Sections are **category-grouped** (Sports, Pro Baseball, Crypto, Video Games…), each with a `▸ See all`.
- Right rail = **ranked discovery**: Trending, Top movers, New, Highest volume — each row shows rank, title, %, and ▲/▼ delta in green/red.

### 3a. Market Card (the core repeating unit — Kalshi rows + our AI badge)

```
┌──────────────────────────────────────────────┐
│ [icon] SPORTS                    Intl Friendlies│
│ Lakers vs Celtics                              │
│ Jan 15 @ 8:00PM                                │
├──────────────────────────────────────────────┤
│ 🟣 Lakers     1.52x          ┌──────┐         │
│                              │ 64% │ ← pill   │
│ 🟢 Celtics    2.36x          └──────┘ 36%     │
│ ⚪ Tie        4.31x                    —       │
├──────────────────────────────────────────────┤
│ 🤖 AI: Lakers 68%  ·  edge +4%   [why?]       │  ← OUR DIFFERENTIATOR
├──────────────────────────────────────────────┤
│ $29,270 vol      ·      3 markets              │
└──────────────────────────────────────────────┘
```
- Outcome rows show **team/flag/avatar + multiplier (`1.52x`) + a bold % pill** (mix of both platforms).
- Hover lifts the card, border → cyan, shows a quick **Buy** affordance per row.
- The **AI row** is unique to us: model %, computed edge (green if positive), and a `why?` link to the reasoning popover.

---

## 4. MARKET DETAIL + TRADING (Polymarket-style, the page that must feel premium)

```
┌── MAIN (≈68%) ───────────────────────────────────┐ ┌── TRADE (≈32%) ──────┐
│ Lakers vs Celtics                         [⋮][↗] │ │  Buy ┃ Sell           │
│ Will the Lakers win?            closes in 6h 23m │ │  ┌─Yes 65¢─┬─No 35¢─┐  │
│                                                  │ │  │ selected         │  │
│  ┌── BIG ANIMATED CHART ──────────────────────┐  │ │  Shares [ 10    ]     │
│  │  68¢ ▲2.3%                                 │  │ │  ───────────────      │
│  │     ╱╲      live candlesticks / area       │  │ │  Avg price   65¢      │
│  │    ╱  ╲╱╲   (toggle), updates in real time │  │ │  Cost        $6.50    │
│  │  ╱╲╱      ╲                                 │  │ │  To win      $10.00   │
│  │ [1H][6H][1D][1W][ALL]   [candles|area]     │  │ │  Potential   +$3.50   │
│  └────────────────────────────────────────────┘  │ │                       │
│  Vol 24h $2.4M · 3.2K traders · last 2m ago      │ │  [  Buy Yes  ]  green  │
├──────────────────────────────────────────────────┤ │  balance after $99,993│
│ ORDER BOOK            │  🤖 AI FORECAST           │ └──────────────────────┘
│ Bids(YES) │ Asks(NO)  │  Lakers 68% (±4%)         │
│ 66¢  1.2K │ 35¢ 2.3K  │  Strong home form;        │
│ 65¢  3.4K │ 34¢ 1.1K  │  Celtics G injured.       │
│ 64¢   800 │ 33¢ 5.2K  │  Brier 0.18 · updated 2h  │
├──────────────────────────────────────────────────┤
│ [Holders] [Activity] [Comments] [About]  ← tabs   │  (Polymarket-style)
│  Holders: avatars + share counts                  │
│  Activity: live trade feed (who bought what)      │
│  Comments: threaded discussion                    │
└──────────────────────────────────────────────────┘
```

Key points:
- **Chart dominates** the top — large, not the small weak Kalshi multi-line. Default **smooth area** (Polymarket feel) with a **candlestick toggle** (trader feel).
- Trade panel is **sticky on the right** with YES/NO tabs, share count, cost, "to win", and live balance — pure Polymarket clarity.
- Order book + AI forecast sit side by side. **Holders / Activity / Comments / About** tabs below (Polymarket's engagement loop).

---

## 5. THE CHART — "moving and dynamic" (your #1 ask)

Library: **TradingView Lightweight Charts** (`lightweight-charts`) — free, 45kb, butter-smooth, designed exactly for this.

Behavior:
- **Two render modes, toggle:** smooth **Area** (gradient fill under line, Polymarket look) and **Candlestick** (trader look). Default = Area.
- **Live updates:** websocket pushes each trade → `series.update()` animates the last point/candle in place (no full redraw flicker). New candle slides in on interval boundary.
- **Crosshair on hover:** floating tooltip with price, time, volume; price axis label tracks the cursor.
- **Range tabs:** `1H · 6H · 1D · 1W · ALL` with a quick fade/zoom transition.
- **Price header animates:** big `68¢` value tweens; the `▲2.3%` delta flashes green/red on change and pulses.
- **Volume histogram** as a subtle pane under price.
- Reduced-motion fallback: respect `prefers-reduced-motion` → disable pulse, keep updates instant.

This replaces the static Kalshi-style line entirely. It should feel alive even when idle (subtle last-candle wick flicker on new trades).

---

## 6. AUTH & ONBOARDING (Kalshi "verify identity" vibe, no real KYC)

- **Signup card** (max 420px): email, password (strength meter), confirm, terms + paper-trading disclaimer checkbox → "Create account".
- **Onboarding progress bar** like Kalshi's "Step 2 of 4": (1) account → (2) confirm email → (3) tutorial → (4) **$100k paper balance granted**. Shown as `▓▓▓░ 2/4` on the home hero until complete.
- Login card: email, password, forgot link.

---

## 7. PORTFOLIO / DASHBOARD

- Top metric cards: **Balance · Total P&L · Win rate · ROI** (P&L green/red).
- **P&L line chart** over time (same lightweight-charts area style) with `7D/30D/90D/ALL`.
- **Open positions** table: market · side · shares · avg entry · current · unrealized P&L.
- **History** table: date · market · side · qty · price · realized P&L.

---

## 8. PROFILE & SOCIAL

- Public profile `@username`: verified badge, member since, stats (trades, P&L, win rate, ROI), volume, followers.
- Read-only recent trades; **Copy positions** CTA (Polymarket-style social trading).
- Leaderboard page: rank by ROI / volume / win rate, gold/silver/bronze for top 3.

---

## 9. ADMIN (you)

- **Markets:** create / edit / **resolve**, import from odds API, pause/cancel.
- **Users:** list, balance, trades, P&L, actions.
- **Reports:** Brier by market, drift alerts, DAU/volume/retention, API/db health.

---

## 10. Components

- **Buttons:** primary (green, white text, brighter on hover), sell (red), secondary (cyan outline → fill on hover), ghost.
- **Outcome pill:** rounded, bold mono %, colored by side.
- **Cards:** `surface` bg, `border`, radius 12, hover → cyan border + lift shadow.
- **Inputs:** dark, cyan focus ring, mono for numeric.
- **Badges:** Open(green) / Closing soon(amber) / Resolved(gray) / Verified(green ✓) / 🤖 AI.
- **Toasts:** slide-in top-right on order fill / error.

---

## 11. Animations & micro-interactions

- Chart live update + price pulse (section 5).
- Outcome % changes flash green/red + count-up tween.
- Order submit: button → spinner "Processing…" → success toast + row fades into Activity.
- Balance count-up animation on change.
- 🔥 pulses on trending rows; volume counters tick up.
- Card hover lift; tab underline slide.
- All gated by `prefers-reduced-motion`.

---

## 12. Responsive

- **Desktop ≥1280:** full 3-zone (grid center + right rail; detail = chart + sticky trade panel).
- **Tablet 768–1279:** 2-zone (drop right rail into a "Discover" drawer; trade panel below chart).
- **Mobile <768:** single column; trade panel becomes a **bottom sheet** ("Trade" FAB); chart full-width; rails become horizontal scroll chips.

---

## 13. Tech & libraries

| Need | Choice |
|---|---|
| Framework | Next.js 15 (App Router) + React 19 |
| Styling | Tailwind CSS + design tokens (section 1) |
| Charts | **lightweight-charts** (price), Recharts (P&L/simple) |
| Realtime | WebSocket (`/ws/markets/:id`) → chart + order book + activity |
| State | React Query (server) + Zustand (UI/trade ticket) |
| Icons | lucide-react |
| Animation | Framer Motion (UI), native series.update (chart) |
| Auth | JWT (httpOnly cookie) + client session |

---

## 14. Build order (frontend)

1. Tokens + Tailwind config + header/nav shell.
2. Market **card** component + category grid + right ranked rails (home).
3. Auth pages + onboarding progress.
4. **Market detail**: animated chart (the centerpiece) + sticky trade panel.
5. Order book + AI forecast + Holders/Activity/Comments tabs.
6. WebSocket wiring → live chart/book/activity.
7. Portfolio dashboard.
8. Profile + leaderboard.
9. Admin.
10. Mobile bottom-sheet + responsive pass.

---

## 15. Definition of "looks like Kalshi+Polymarket, not a demo"

- [ ] Home is a **category-grouped grid** with multi-outcome cards (odds + %), not a flat list.
- [ ] **Ranked right rail** (Trending / Top movers / Highest volume / New) with ▲▼ deltas.
- [ ] Market detail leads with a **large, smoothly animated, live-updating chart** (area+candle toggle).
- [ ] **Sticky YES/NO trade panel** with shares, cost, "to win", live balance.
- [ ] **Holders / Activity / Comments** tabs populated with real data.
- [ ] Every market shows an **🤖 AI % + edge** badge (our differentiator).
- [ ] Dark theme, green/red semantics, mono numerics throughout.
- [ ] Fully responsive incl. mobile bottom-sheet trading.
```
