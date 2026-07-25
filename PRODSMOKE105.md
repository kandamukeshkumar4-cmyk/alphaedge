# PRODSMOKE105 — Wave 105 post-deploy production smoke

**Mode:** READ-ONLY (GET only). No POST/PUT/DELETE, no deploy, no mutations.  
**API:** `https://alphaedge-api-production-b9db.up.railway.app`  
**Frontend:** `https://alphaedge-frontend-three.vercel.app`  
**Probed:** 2026-07-25 (UTC headers from Railway/Vercel)  
**Baseline cross-ref:** `GAPMAP104.md` (pre-wave surface survey, same API host)

Orchestrator already confirmed (not re-argued):  
`/api/v1/social/stories` → 200 with derived stories;  
`/api/v1/watchlist/shared/demo` → 404 (contract);  
`/health` `paper_trading_only: true`.

---

## VERDICT: HEALTHY

Wave 105 surfaces are live in production. Previously-dead FE routes return **200** with real product shells (not empty 404 pages). Social stories contract + cursor pagination hold against real prod data (including timestamp collisions). Core research APIs return non-empty payloads; no 5xx observed. Paper guardrail intact. Community client no longer ships fabricated story fixtures.

Minor non-blocking notes (not enough to DEGRADE the wave):
- `/api/v1/eval/calibration` is **200 but zero-filled bins** (path fixed; signal hollow).
- Live **CommentOut** body not exercised (empty `items:[]` for sampled story).
- OpenAPI marks `GET /social/stories` with `HTTPBearer` while anonymous GET succeeds (optional-auth for `reacted`; public feed works).

---

## Route + endpoint table

| path | status | time (ms) | real content? | notes |
| --- | ---: | ---: | --- | --- |
| **FE** `/traders` | **200** | 314–607 | **Yes (shell + live client)** | Was dead/404 pre-deploy. HTML ~47KB; UI copy: “Find a trader”, “Loading trader rankings”, “Classic leaderboard”, sort controls. JS chunk wires `/api/v1` + leaderboard. **No longer 404.** |
| **FE** `/library` | **200** | 96–460 | **Yes (shell + live client)** | HTML ~50KB; “Loading research library”, library-filter-* chips (brief/report/scanner/alpha/workflow). |
| **FE** `/community` | **200** | 113–153 | **Yes (shell + live client)** | HTML ~44KB; `main#community-feed`, “Community desk”, “Stories from the desk”, loading skeleton `aria-label="Loading community stories"`. Client calls `/api/v1/social/stories`; honest offline copy (see truthfulness). |
| **FE** `/traders/Trader-cd1dca` | **200** | 226–458 | **Yes (detail shell)** | Route param present in RSC payload; “Loading trader detail”. Backing API profile 200 (below). |
| **FE** `/traders/demo` | **200** | 458 | Shell | Detail route alive (not 404); name “demo” may 404/empty after client fetch — route itself is not dead. |
| **FE** `/trade` | **200** | 255 | Yes | Paper copy only; no funding rails language. |
| **FE** `/w/demo` | **200** | 96–234 | Shell | “Loading shared watchlist”; API shared/demo correctly 404. |
| **API** `/health` | **200** | 351 | Yes | `paper_trading_only: true` (see paste). |
| **API** `/api/v1/markets` | **200** | 270–315 | Yes | Default page: **100** items, **~127KB**, headers `x-total-count=1630`, `x-page-limit=100`, `x-page-offset=0`. |
| **API** `/api/v1/markets?limit=5` | **200** | ~ | Yes | **6472B**; `x-page-limit=5`, `x-total-count=1630`. Limit **honored** (GAPMAP104: limit ignored, ~2.3MB). |
| **API** `/api/v1/markets?limit=5&offset=5` | **200** | 207 | Yes | 5 items; `x-page-offset=5`; first slug `pm-will-norway-win-the-2026-fifa-world-cup-893`. |
| **API** `/api/v1/signals/dashboard` | **200** | 989 | Yes | Non-empty `signals[]`; `paper_trading_only: true`. ~42KB. |
| **API** `/api/v1/home` | **200** | 1597 | Yes | `authenticated:false` + signals present. Under 3s. |
| **API** `/api/v1/feed` | **200** | 270 | Yes | Non-empty `items[]`. |
| **API** `/api/v1/screener` | **200** | 567 | Yes | Non-empty `items[]` (Argentina WC etc.). |
| **API** `/api/v1/alpha/report` | **200** | 646 | Yes | Honest `model_edge` REJECTED vs closing (t≈-3.19, n=154). |
| **API** `/api/v1/leaderboard` | **200** | 246 | Yes | 1 entry (`Trader-cd1dca`) — same shape as GAPMAP104. |
| **API** `/api/v1/track-record` | **200** | 749 | Yes | `n:202`, Brier ~0.073, calibration bins present. |
| **API** `/api/v1/social/stories` | **200** | 236 | Yes | 20 items + `next_cursor`; real trade-derived stories. |
| **API** `/api/v1/social/stories?limit=2` | **200** | 261–444 | Yes | 2 items + cursor. |
| **API** `/api/v1/social/stories/{id}/comments` | **200** | 207 | Empty list | `{"items":[]}` for `trade:27dac59b-…` (valid empty). |
| **API** `/api/v1/social/traders/Trader-cd1dca` | **200** | 224 | Yes | Public profile + `paper_trading_only: true`. |
| **API** `/api/v1/social/following` | **401** | 411 | Auth gate | Anonymous blocked (expected). |
| **API** `/api/v1/social/feed` | **401** | 174 | Auth gate | Anonymous blocked (expected). |
| **API** `/api/v1/watchlist` | **401** | — | Auth gate | Anonymous blocked. |
| **API** `/api/v1/portfolio` | **401** | — | Auth gate | Anonymous blocked. |
| **API** `/api/v1/watchlist/shared/demo` | **404** | 266 | Contract OK | Matches orchestrator / share contract. |
| **API** `/api/v1/eval/calibration` | **200** | 211 | Path OK / data hollow | Bins all `count:0` — not a 5xx; calibration path reachable. |
| **API** `/openapi.json` | **200** | 697 | Yes | Used for auth class + schemas. |

**No request exceeded ~3s** on this pass (slowest: `/api/v1/home` ~1.6s, signals dashboard ~1.0s).

### Evidence pastes (status / JSON fragments)

**Health:**
```json
{"status":"ok","paper_trading_only":true,"disclaimer":"This project is a paper-trading simulation for sports and election markets using simulated funds for research and portfolio demonstration only."}
```

**Story sample (anon `reacted: false`):**
```json
{
  "id": "trade:27dac59b-b4d2-4e89-a770-b2304aec921c",
  "kind": "trade",
  "actor": {"handle": "Trader-cd1dca", "display_name": "Trader-cd1dca", "avatar_url": null},
  "market_slug": "pm-will-argentina-win-the-2026-fifa-world-cup-245",
  "market_title": "World Cup Winner: Will Argentina win the 2026 FIFA World Cup?",
  "headline": "YES yes 1 @ 0.1745 on pm-will-argentina-win-the-2026-fifa-world-cup-245",
  "body": null,
  "created_at": "2026-07-14T00:30:14.015376Z",
  "reactions": {"like": 0},
  "reacted": false,
  "comment_count": 0
}
```

**Comments for that story:**
```json
{"items":[]}
```

**Alpha `model_edge` (honest reject + real t-stat):**
```json
{"name":"model_edge","valid":false,"reason":"oos_does_not_beat_closing","count":154,"t_stat":-3.193043,"oos_brier":0.120906,"closing_brier":0.042561,"brier_delta_vs_closing":-0.078345}
```

**Trader profile:**
```json
{"username":"Trader-cd1dca","member_since":"2026-07-14T00:30:12.212831Z","trade_count":1,"settled_trade_count":1,"win_rate":0.0,"roi":-1.0,"followers_count":0,"following_count":0,"paper_trading_only":true}
```

**Markets pagination headers (`?limit=5`):**  
`x-total-count=1630`, `x-page-limit=5`, `x-page-offset=0`, body length **6472** (not multi-MB dump).

---

## Contract conformance (Story / Comment)

### StoryOut — live vs required checklist

| field | required by brief | live present? | notes |
| --- | --- | --- | --- |
| `id` | yes | yes | e.g. `trade:27dac59b-…` |
| `kind` | yes | yes | `"trade"` (OpenAPI enum: trade/forecast/watchlist/note) |
| `actor` | yes | yes | object |
| `actor.handle` | yes | yes | |
| `actor.display_name` | yes | yes | |
| `actor.avatar_url` | yes | yes | may be `null` (OpenAPI allows null) |
| `market_slug` | yes (brief) | yes | OpenAPI: optional/nullable; live trade stories populate it |
| `market_title` | yes (brief) | yes | same |
| `headline` | yes | yes | |
| `body` | yes (brief) | yes | value **`null`** on sampled trades (allowed by OpenAPI) |
| `created_at` | yes | yes | ISO timestamp string |
| `reactions` | yes | yes | |
| `reactions.like` | yes | yes | integer count (e.g. `0`) |
| `reacted` | yes | yes | **`false` for all 20 default-feed items** as anonymous |
| `comment_count` | yes | yes | integer |

**Missing fields on live stories:** none of the brief-required keys.  
**Extra fields on live stories:** none beyond the required set.  
**StoryPageOut:** live keys `items`, `next_cursor` (matches OpenAPI `StoryPageOut`).

Full default feed (n=20): field audit = **ALL_STORIES_MATCH_REQUIRED_FIELDS**; `reacted_false_all=True`.

### CommentOut

OpenAPI `CommentOut` requires: `id`, `actor`, `body`, `created_at`.  
Live list shape: `CommentListOut` = `{"items":[]}`.  
**No live comment row available → CommentOut instance fields UNVERIFIED** (endpoint + empty envelope verified).

---

## Pagination walk

**Request:** `GET /api/v1/social/stories?limit=2` then follow `next_cursor` (URL-encoded) for pages 2–3.

| page | ids | created_at | next_cursor |
| ---: | --- | --- | --- |
| 1 | `trade:27dac59b-b4d2-4e89-a770-b2304aec921c` | 2026-07-14T00:30:14.015376Z | `2026-07-11T11:28:28.245805Z\|trade:998c90bd-b660-4b64-a630-a7eae0da5c86` |
| 1 | `trade:998c90bd-b660-4b64-a630-a7eae0da5c86` | 2026-07-11T11:28:28.245805Z | (same) |
| 2 | `trade:2765979c-75d7-494e-85f7-69a83f893c21` | 2026-07-11T11:28:28 (same second as p1 tail) | `2026-07-11T10:20:29.281496Z\|trade:3b0a4ce0-e768-4f4f-aa6f-fe60a3f52bc7` |
| 2 | `trade:3b0a4ce0-e768-4f4f-aa6f-fe60a3f52bc7` | 2026-07-11T10:20:29.281496Z | |
| 3 | `trade:1f0deb1f-8f75-431a-a5fb-fa7a9edd98bb` | 2026-07-11T10:20:29 (collision with p2 tail) | `2026-07-10T23:32:34.584062Z\|trade:db7f2d8d-d65d-483b-aace-b461c3a3b981` |
| 3 | `trade:db7f2d8d-d65d-483b-aace-b461c3a3b981` | 2026-07-10T23:32:34.584062Z | |

**Overlap:** **NONE** across 6 ids (pre-merge cursor bug would double-emit under timestamp ties).  
**Gaps:** Cursor is composite `timestamp|id`. Same timestamps correctly appear on adjacent pages with **different** ids — this is tie-break continuation, not a missing-row gap. Order is strictly non-increasing by time, then by id cursor.  
**All `reacted` on pages 1–3:** `false`.

Default feed (limit default, n=20) also returns `next_cursor`, confirming more pages exist beyond the first window.

---

## Regressions vs pre-deploy (GAPMAP104)

| surface | GAPMAP104 | PRODSMOKE105 | regression? |
| --- | --- | --- | --- |
| `/traders` FE | EXCLUDED / dead workstream (0-byte / 404 history) | **200 real shell** | **Fixed** (ship goal) |
| `/library` FE | EXCLUDED thin hub | **200 real shell** | **Fixed** (ship goal) |
| Community/social | assigned / not live inventory | stories **200**, FE `/community` **200** | **New surface healthy** |
| `GET /markets` size | **~2.3MB · ~2.3s**, limit ignored | default **~127KB / 100 rows**, `?limit=5` **~6.5KB** + `X-Total-Count` | **Improved** (pagination) |
| `/api/v1/home` | 200 · signals · ~999ms | 200 · signals · ~1597ms | OK (under 3s) |
| `/api/v1/signals/dashboard` | 200 · ~40KB | 200 · ~42KB | OK |
| `/api/v1/screener` | 200 non-empty | 200 non-empty | OK |
| `/api/v1/feed` | 200 items | 200 items | OK |
| `/api/v1/leaderboard` | 200 · 1 entry | 200 · 1 entry | OK |
| `/api/v1/track-record` | 200 data | 200 `n=202` | OK |
| `/api/v1/alpha/report` | 200 hollow/invalid factors | 200 + **real t_stat / REJECTED vs close** | **Improved honesty** (not empty regression) |
| `/health` paper flag | true | true | OK |

**No REGRESSION of the form “previously returned data, now empty/5xx”** on the checked existing surfaces.

---

## Paper-guardrail + truthfulness findings

### Paper guardrail
- `/health`: **`paper_trading_only: true`** (paste above).
- Signals dashboard includes `"paper_trading_only":true` and research disclaimer.
- Social trader profile includes `"paper_trading_only":true`.
- FE HTML (community, trade, traders, library): repeated disclaimer  
  *“This project is a paper-trading simulation … simulated funds … demonstration only.”*  
  Meta `paper-trading-disclaimer` present.
- **No matches** in probed FE HTML for: `real money`, `fund your`, `deposit`, `withdraw`, `cash out`, `live trading`, `execute order` (as funding/execution rails copy).
- `/trade` meta/description: “Paper trade prediction markets with simulated funds.”

### Truthfulness (community feed — no fabricate-on-failure)
- HTML grep: **`demo-trader` = 0**, **`Lakers vs Celtics` = 0**, **`MOCK_STORIES` = 0**.
- Deployed community JS (`/_next/static/chunks/app/community/page-612c2f4fdbc1bb54.js`, 24188 bytes):
  - `demo-trader` / `Lakers vs Celtics` / `MOCK_STORIES` / `mockStories` = **0**
  - Calls **`/api/v1/social/stories`** (5 refs), `next_cursor` (5), `Load more` (1)
  - Honest offline string (literal in bundle):  
    **“The feed could not be loaded. Nothing fabricated is shown while the community service is offline.”**  
    plus `community-empty-state`
- Live API returns **real derived trade stories** (e.g. Trader-cd1dca Argentina WC trade), not invented Lakers desk fiction.
- SSR HTML shows loading skeleton until client fetch — not a fabricated story list.

---

## Anonymous safety

| check | result |
| --- | --- |
| `reacted` on stories (anon) | **false** on all items in default feed (20/20) and pages 1–3 of limit=2 walk |
| USER-auth GETs without token | `GET /watchlist` → **401**; `GET /portfolio` → **401**; `GET /auth/me` → **401**; `GET /social/following` → **401**; `GET /social/feed` → **401** |
| Mutation routes | **Not POSTed** (rule). OpenAPI auth classes below. |

### OpenAPI auth class (docs evidence)

| method + path | OpenAPI `security` | runtime GET (anon) |
| --- | --- | --- |
| GET `/api/v1/social/stories` | `HTTPBearer` | **200** (public feed; bearer optional for user `reacted`) |
| GET `/api/v1/social/stories/{id}/comments` | none | **200** |
| POST comments / reactions / DELETE reaction | `HTTPBearer` | UNVERIFIED by design (no POST) |
| GET `/api/v1/social/following` | `HTTPBearer` | **401** |
| GET `/api/v1/social/feed` | `HTTPBearer` | **401** |
| POST/DELETE `/api/v1/social/follow/{trader}` | `HTTPBearer` | not exercised |
| GET `/api/v1/watchlist` | `HTTPBearer` | **401** |
| GET `/api/v1/watchlist/shared/{handle}` | none | **404** for `demo` |
| POST `/api/v1/watchlist/share` | `HTTPBearer` | not exercised |

---

## UNVERIFIED

1. **Live CommentOut row fields** — comments list always empty for sampled story; schema known from OpenAPI only.  
2. **POST/DELETE mutation auth enforcement at runtime** — GET-only policy; OpenAPI + related 401 GETs support “auth required,” but reaction/comment write path not hit.  
3. **Client-rendered story list in browser after hydration** — verified via API + JS bundle + SSR shell; no headless browser paint.  
4. **Shared watchlist with a real public handle** — only `demo` checked (404 correct); positive shared-watchlist case not found without inventing handles.  
5. **Whether OpenAPI `HTTPBearer` on GET stories is intentional optional security** — docs say bearer; anon works. Document mismatch, not a prod outage.  
6. **A11y / source-labelling “8 surfaces” exhaustive audit** — out of this smoke’s network contract checks (not GET-provable as a set).

---

## AutoLab

AutoLab: not applicable (no iterative measure) — one-shot post-deploy verification.

---

*End PRODSMOKE105 — evidence from live GETs only.*
