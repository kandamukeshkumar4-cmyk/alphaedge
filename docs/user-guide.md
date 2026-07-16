# AlphaEdge user guide

> **Paper-trading only.** AlphaEdge is a prediction-market **simulation**.
> Balances, orders, P&L, and leaderboard ranks use **simulated funds**. There
> are no deposits, withdrawals, or real-money rails. The backend requires
> `PAPER_TRADING_ONLY=true`.

This guide describes what a human user can do in the **Next.js frontend**
(`frontend/src`) against the live API. Every screen and flow below is checked
against code; features that exist only as APIs (not yet wired in UI) are marked
explicitly.

Related: [API reference](./api.md) · [Operations](./operations.md) ·
[Methodology](./methodology.md).

---

## 1. Create an account (signup)

| Step | Where |
|------|--------|
| Open signup | `/auth/signup` (`frontend/src/app/auth/signup/page.tsx`) |
| Submit | `POST {API}/api/v1/auth/signup` with email + password (`credentials: "include"` for httpOnly cookie) |
| Success | Stores access token locally via `saveAuthSession`, redirects to **`/portfolio`** |
| Login | `/auth/login` → `POST /api/v1/auth/login` |

**Rules verified in UI/API:**

- Password must be **≥ 8** characters; confirm must match; must accept terms.
- Email uniqueness → API `409` “Email already registered”.
- Session: Bearer token **and** httpOnly cookie `ae_access` (Bearer wins if both present).

**Starting paper balance:** new users get **`$100,000`** simulated cash
(`User.paper_balance` default `Decimal("100000")` in `backend/app/db/models.py`).
Onboarding copy in `OnboardingModal` matches this figure.

---

## 2. Discover markets (trending vs Longshots / Decided)

### Home / Discover

- Route **`/`** is the Discover home (`app/page.tsx`).
- Server loads markets with **`fetchMarkets({ sort: "active" })`** →
  `GET /api/v1/markets?sort=active`.
- `/discover` **redirects to `/`** (alias only).

### Trending (active board)

The markets board filters to **active trending** markets via
`activeTrendingMarkets()` in `frontend/src/lib/live-discovery.ts`:

| Kept only if… | Meaning |
|---------------|---------|
| `status` open (or unset) | Not locked/resolved |
| YES price in **(0.01, 0.99)** | Not a near-certain “decided” price |
| `endsAt` still in the future (when parseable) | Not past close |

Topic chips (including **Trending**) come from `KALSHI_TOPICS` in
`frontend/src/lib/kalshi-topics.ts`. The left rail shows top traders, trending
markets, and live signals (`QuestSignalRail`).

### Longshots / Decided

The chip **“Longshots / Decided”** is a **link to `/resolved`**, not another
sort of the open board (`QuestDiscoverShell`, `QuestMarketsBoard`,
`QuestLiveMarketsBoard`).

`/resolved` is a **read-only** review of resolved markets
(`GET /api/v1/resolved`): model prediction vs real outcome, per-market Brier.
It is **not** an order feed.

---

## 3. Signals, briefs, and research

| Screen | Route | Data source |
|--------|-------|-------------|
| Signals dashboard | `/signals` | `GET /api/v1/signals/dashboard`, arb opportunities, signal events |
| Research / briefs | `/research` | `GET /api/v1/briefs` (honest empty if API down — no mock list) |
| Brief detail | `/research/brief?id=…` | `GET /api/v1/briefs/{id}` |
| Track record (analyst claims) | `/track-record` | `GET /api/v1/analyst/track-record` + graded claims |
| Model track record | uses `/api/v1/track-record` | Calibration/Brier/CLV from **real resolutions only** |
| Opportunities | `/opportunities` | Ranked model-vs-market edges; deep-links to market paper-trade panel |
| Feed | `/feed` | Cross-market stream of signals / briefs / activity |
| Smart money | `/smart-money` | Smart-money panel |
| Alerts | `/alerts` | See §7 |

**Important product rules (from UI copy + backend):**

- Signals and opportunities are **research / analysis**, not automatic orders.
- Alerts **notify only** — they never place trades (`alerts/page.tsx` header).
- Analyst track-record claims can show **PROVISIONAL** when sample size is low
  (`n` / graded-claims threshold in UI).

---

## 4. Place a paper trade

### Where to trade

| Entry | Notes |
|-------|--------|
| Market detail | Trading panel on `/markets/[slug]` (`MarketTradingPanel`) |
| Trade terminal | `/trade?slug=…` (`TradeTerminal`) |
| First-bet onboarding | Suggests a liquid market and deep-links into paper trade |

### What happens on submit

1. You must be logged in (JWT).
2. UI calls `placePaperOrder` → **`POST /api/v1/orders`** with body
   `{ slug, side, outcome, shares, price }` and header **`Idempotency-Key`**
   (one key per click intent; retries do not double-debit).
3. Backend enforces:
   - `PAPER_TRADING_ONLY=true`
   - Market exists, not already resolved, status **open**, not past `lock_at`
   - Optional price band vs latest non-seed odds snapshot (±0.10)
   - Atomic debit of `users.paper_balance`
4. Response always marks **`paper_trading_only: true`**.

### Closing a position

- UI uses **`POST /api/v1/positions/close`** (also idempotent).
- There is **no** human-path “cancel resting limit order” — the JWT ledger is
  immediate paper open/close, separate from the agent CLOB cancel path
  (`POST /api/v1/orders/{id}/cancel`).

---

## 5. Portfolio (P&L, risk, CLV)

Route: **`/portfolio`** (requires login; redirects to `/auth/login` if not).

| UI panel | API |
|----------|-----|
| Portfolio value, paper balance, unrealized / realized P&L, positions table | `GET /api/v1/portfolio` |
| Trade history tab | `GET /api/v1/orders/history` |
| CLV distribution | `GET /api/v1/portfolio/clv-summary` (`PortfolioClvPanel`) |
| Exposure groups | `GET /api/v1/portfolio/exposure` |
| Risk metrics (win rate, max drawdown, per-trade Sharpe, category exposure) | `GET /api/v1/portfolio/risk` |
| Trader profile card | `GET /api/v1/profile` |

### Equity curve & attribution (API vs UI)

| Capability | Status |
|------------|--------|
| `GET /api/v1/portfolio/equity-curve` | **Exists on API** (JWT) |
| `GET /api/v1/portfolio/attribution` | **Exists on API** (JWT) |
| Portfolio page charts for those two | **Not wired** in `portfolio/page.tsx` as of this doc |
| Equity curve chart component | Used on **`/backtest`** for backtest replay equity, not live user portfolio |

Unrealized P&L uses latest odds marks when available; settled positions zero out
mark-to-market fields. Transient DB failures surface as **503** “temporarily
unavailable” rather than an empty zeroed book.

---

## 6. Leaderboard

Route: **`/leaderboard`**.

- Data: `GET /api/v1/leaderboard` (`limit`, `offset`, `sort`, default
  `realized_pnl`).
- Ranks paper traders by **realized P&L** (and related ROI / win rate fields).
- Empty state: rankings appear after paper orders settle — place a trade to
  appear.
- If the API is unreachable, UI may show **demo standings** with an explicit
  “Showing demo standings” notice (not live ranks).

---

## 7. Alerts & watchlist

### Alerts (`/alerts`)

- Public feed: `GET /api/v1/alerts/feed` (and related digest).
- When signed in, **Watchlist** scope uses `GET /api/v1/watchlist/alerts`.
- Family filters + optional notify prefs (`GET/PUT /api/v1/notify/prefs`).
- Alerts are **notifications only** — no order submission from this page.

### Watchlist (`/watchlist`)

- JWT: `GET/POST /api/v1/watchlist`, `DELETE /api/v1/watchlist/{slug}`.

### Notification bell (header)

Component: `frontend/src/components/NotificationBell.tsx` (mounted from
`SiteHeader`). API client: `frontend/src/lib/notifications-api.ts`.

| Behavior | Detail |
|----------|--------|
| Who sees data | **Signed-in users only** (JWT). Logged-out: bell opens a “log in to see notifications” prompt. |
| List | `GET /api/v1/notifications` → items + **`unread_count`** badge |
| Mark one / all | `POST /api/v1/notifications/{id}/read`, `POST /api/v1/notifications/read-all` (idempotent) |
| Live updates | Optional WS subscribe helper in the client (in-app channel only) |
| Delivery | **In-app only** — no email, SMS, or push. Backend disclaimer on list responses. |

These are distinct from the public **Alerts** page (`/alerts`), which is a
research/signal feed, not a private inbox.

---

## 7b. Trader profiles & following

| Surface | Route / API | Auth |
|---------|-------------|------|
| Public profile | `/traders/[name]` → `GET /api/v1/social/traders/{trader}` | Public |
| Follow / unfollow | `POST` / `DELETE /api/v1/social/follow/{trader}` | JWT (login redirect if needed) |
| Following list | `GET /api/v1/social/following` | JWT |
| Following activity | `/feed?view=following` → `GET /api/v1/social/feed` | JWT |
| Leaderboard entry points | `/leaderboard` links into `/traders/{username}` | Public |

**Rules (code-verified):**

- Profiles show **anonymized** paper stats (username/label, win rate, ROI,
  followers) — **no email or user id** (`backend/app/api/v1/social.py`).
- Self-follow is rejected (`400`).
- Follow is **social only** — it does **not** auto-copy trades or place orders.
- UI: `frontend/src/app/traders/[name]/page.tsx`, `frontend/src/lib/social-api.ts`,
  feed toggle in `frontend/src/app/feed/page.tsx`.

---

## 7c. Eval / proof page (`/eval`)

Route: **`/eval`** (`frontend/src/app/eval/page.tsx`). Also linked from Home and
the header “More” menu (`HeaderMoreMenu`).

| Panel | Data source | Notes |
|-------|-------------|-------|
| Mean Brier / calibration error / market count | `GET /api/v1/eval/aggregates` | Public; “Start the API…” empty state if offline |
| ForecastScore drift series | `GET /api/v1/eval/drift` via `DriftSeriesPanel` / `eval-api.ts` | Public read-only snapshots |
| LightGBM vs XGBoost A/B | `ModelAbCard` → `GET /api/v1/system/model-ab` + `GET /api/v1/system/resolved-count` | **Analysis only** — `applied` never true |
| Model registry list (read) | admin-gated models API when key present in admin tools | Activate/rollback are **admin**, not this page |
| Ensemble vs single (U08) | optional `GET /api/v1/ensemble/autolab` | Honest “not yet measured” / not_run when missing or flag off |

**Honesty rules shown in UI copy:** never fabricates Brier numbers; ensemble
comparison stays “not measured” until a real walk-forward run; A/B does not
change the deployed default model.

### Resolved-count `source` field (honest population)

Public readout: **`GET /api/v1/system/resolved-count`**
(`backend/app/api/v1/system.py` → `resolved_outcomes_breakdown` in
`backend/app/ml/ab_harness.py`).

| Field | Meaning |
|-------|---------|
| `resolved_count` | Count used for the A/B **eligibility** gate (same definition as before) |
| `ab_threshold` / `ab_ready` | Whether walk-forward A/B may run; **never flips** `model_default` |
| `source` | **`forecast_scores`** if count comes from scored pre-close LIVE forecasts; **`paper_orders_fallback`** if no scored forecasts exist and the API fell back to resolved paper-order markets |
| `forecast_scored_count` | Size of the forecast-scored population (0 under fallback) |

**Why it matters:** the forecast autolock / bridge loops accrue the
`forecast_scores` population. A high `resolved_count` under
`paper_orders_fallback` is a **different** population — useful for progress UI,
but not proof that model forecasts have been locked and graded. The `/eval`
A/B card uses `resolved_count` for the progress bar; treat `source` as the
disclosure of *which* sample filled that bar.

---

## 8. How numbers accrue (honest lifecycle)

This is the most important section for interpreting “empty” track records and
slow-moving P&L.

### A. Human paper trading (JWT ledger)

```text
Browse open market
  → Place paper BUY (balance debit, PaperOrder row)
  → Hold while market open (unrealized P&L vs latest odds)
  → Optional CLOSE before resolution (SELL, realized_pnl on close)
  → Or wait for market resolve (admin/worker settle credits winners)
  → Leaderboard / portfolio realized metrics update from settled trades
```

Until markets **resolve** (or you close), realized leaderboard stats stay thin.

### B. Forecast / mirror locks (skill tracking)

Mirror/forecast path (`ForecastService.lock_forecast`):

1. **Lock pre-close** — LIVE forecasts can only be locked while the external
   market status is **OPEN**. Probability is append-only (new sequence if you
   update).
2. **Resolve from venue data** — after the real market resolves, scores attach
   to locked forecasts (`ForecastScore` + resolved `ExternalMarket`).
3. **Grade** — Brier / calibration / CLV aggregates use **scored LIVE forecasts
   on RESOLVED markets** (primary), with a paper-order fallback for some
   surfaces. Zero resolutions → `n=0`, thin/provisional flags, empty series —
   **not** fabricated history.

### C. Why track-record starts sparse

| Cause | Effect |
|-------|--------|
| Few markets resolved yet | `n` small; UI shows PROVISIONAL / thin_data |
| Forecasts locked only after close (rejected) | No LIVE row to grade later |
| Leakage-safe scoring waits for real outcomes | No lookahead grading |
| A/B / model default never auto-flips on sparse data | `system/model-ab` reports analysis only (`applied: false`) |

Analyst claims and model track records are graded against **reality**, not
curated highlight reels. Misses render as prominently as wins on
`/track-record` and `/resolved`.

### D. CLV gate honesty

Model forecasts shown on market detail can be marked **provisional** until
walk-forward CLV shows the model beats the closing line
(`ForecastService.predict` → `clv_gate_passed` / `provisional`). A quiet CLV
panel is a correct outcome, not a bug.

---

## 9. Suggested first session

1. Open `/` — scan **Trending** active markets (`sort=active`).
2. Sign up at `/auth/signup` — confirm ~$100k paper balance on `/portfolio`.
3. Open a market (canonical demo: `nba-2025-01-15-lal-bos`) and place a small
   paper trade with YES/NO + share size.
4. Check `/portfolio` positions and risk panels; notice the **notification bell**
   once signed in (order / digest messages stay in-app only).
5. Browse `/signals` and `/research` for context (read-only).
6. Open `/eval` for Brier aggregates + A/B progress (and note `source` honesty
   on resolved-count when inspecting the API).
7. Peek `/resolved` (Longshots / Decided), `/track-record`, and a
   `/traders/{name}` profile from the leaderboard; optionally **Follow** and
   switch `/feed?view=following`.
8. After more resolved activity, re-check `/leaderboard`.

---

## 10. What this product is not

- Not a real-money exchange or broker.
- Not a guarantee of edge; provisional signals stay provisional until CLV-validated.
- Not auto-trading from alerts, assistant chat, or LLM text — agent CLOB path
  still goes through **RiskService → OrderIntent → OrderBookService** only.

For endpoint-level detail see [docs/api.md](./api.md).
