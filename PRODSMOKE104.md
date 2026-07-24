# PRODSMOKE104 — Post-deploy production smoke (Wave 104)

**Mode:** READ-ONLY against production (GET only). No POST/PUT/DELETE, no mutations, no deploy.  
**When:** 2026-07-24 (UTC window ~22:17–22:20)  
**API:** `https://alphaedge-api-production-b9db.up.railway.app`  
**Frontend:** `https://alphaedge-frontend-three.vercel.app`  
**Baseline reference:** `GAPMAP104.md` (pre-wave surface survey, same day)

Orchestrator already confirmed (extended, not re-litigated):  
`/api/v1/social/stories` → 200 with derived data; `/api/v1/watchlist/shared/demo` → 404 (contract); `/health` `paper_trading_only: true`.

---

## VERDICT: HEALTHY

Wave 104 ship targets are live in production: social stories API (contract + cursor pagination), previously dead `/traders` and live `/library`/`/community` frontend routes, paper flag intact, no 5xx on regression GETs, no evidence of fabricate-on-failure stories in the community page. Residual product hollowness on pre-existing surfaces (alpha factors invalid, markets payload size) matches GAPMAP104 and is **not** a Wave 104 regression.

---

## Route + endpoint table

| path | status | time (ms) | real content? | notes |
| --- | ---: | ---: | --- | --- |
| **Frontend** | | | | |
| `GET /traders` | **200** | 668 | **YES** | SSR text: “Public paper record / Traders, with receipts / Classic leaderboard…”. **No longer 404.** `next404=False`. ~47KB HTML. |
| `GET /library` | **200** | 151 | **YES** | SSR: “Persisted research / Library / Browse the briefs… Every card comes from a live read.” ~50KB. |
| `GET /community` | **200** | 151 | **YES (shell + live client path)** | SSR chrome: “Community desk / Stories from the desk / Paper-market notes…”. Story cards not in SSR (client fetch). No `demo-trader` / `Lakers vs Celtics` / `MOCK_STORIES` in HTML. ~44KB. |
| `GET /traders/Trader-cd1dca` | **200** | 1220 | **YES (thin SSR + live profile)** | HTML contains `Trader-cd1dca`; API profile 200 (see below). |
| `GET /traders/demo` | **200** | 814 | shell/empty profile path | Route alive (not 404 page). API trader `demo` → 404. |
| `GET /traders/demo-trader` | **200** | 203 | shell | Route alive. API `demo-trader` → 404. |
| `GET /w/demo` | **200** | 125 | shell | Shared watchlist page reachable; API shared demo 404 (expected). |
| `GET /trade` | **200** | 219 | YES (chrome + paper disclaimer) | Footer/disclaimer: paper-trading simulation / simulated funds. No deposit/withdraw/real money strings. |
| **API — new social** | | | | |
| `GET /api/v1/social/stories` | **200** | 254 | YES | 20 items default page; `next_cursor` present; derived `trade:…` ids. |
| `GET /api/v1/social/stories?limit=2` | **200** | 214 | YES | Exactly 2 items + cursor. |
| `GET …/stories?limit=2&cursor=…` (p2, p3) | **200** | 334 / 297 | YES | Cursor advances; no id overlap (see Pagination). |
| `GET /api/v1/social/stories/{id}/comments` | **200** | 236 | YES (empty list) | id=`trade:27dac59b-b4d2-4e89-a770-b2304aec921c` → `{"items":[]}`. |
| `GET /api/v1/social/traders/Trader-cd1dca` | **200** | — | YES | `trade_count:1`, `paper_trading_only:true`. |
| `GET /api/v1/social/traders/demo` | **404** | — | n/a | Expected missing handle. |
| `GET /api/v1/watchlist/shared/demo` | **404** | 526 | n/a | Matches orchestrator / contract. |
| `GET /api/v1/social/following` (anon) | **401** | — | auth wall | USER-auth surface not readable anonymously. |
| **API — regressions** | | | | |
| `GET /health` | **200** | 640 | YES | `paper_trading_only:true` (see evidence). |
| `GET /api/v1/markets` | **200** | 1702 | YES (huge) | ~2.35MB; still slow (GAPMAP104 ~2.3s / ~2.3MB). **&lt;3s this pass.** |
| `GET /api/v1/signals/dashboard` | **200** | 981 | YES | Non-empty `signals[]`; paper disclaimer. |
| `GET /api/v1/home` | **200** | 1100 | YES | `authenticated:false` + signals present. |
| `GET /api/v1/feed` | **200** | 286 | YES | Non-empty `items[]`. |
| `GET /api/v1/screener` | **200** | 726 | YES | Non-empty `items[]` (~13KB; GAPMAP noted ~2.4KB — still non-empty). |
| `GET /api/v1/alpha/report` | **200** | 587 | YES but hollow factors | Factors still `valid:false` / `missing_closing_line` — **pre-existing (GAPMAP #3), not emptied.** |
| `GET /api/v1/leaderboard` | **200** | 252 | YES (thin) | 1 entry `Trader-cd1dca` (GAPMAP also 1 entry). |
| `GET /api/v1/track-record` | **200** | 790 | YES | `n:200`, `brier_score≈0.070`. |
| `GET /openapi.json` | **200** | 1727 | YES | Used for auth-class docs. |
| `GET /docs` | **200** | 230 | YES | Swagger UI shell. |

**No 5xx observed** on any sampled GET.

### Evidence fragments (status / JSON)

```text
GET /health → 200
{"status":"ok","paper_trading_only":true,"disclaimer":"This project is a paper-trading simulation for sports and election markets using simulated funds for research and portfolio demonstration only."}
```

```text
GET /api/v1/social/stories?limit=1 → 200
{"items":[{"id":"trade:27dac59b-b4d2-4e89-a770-b2304aec921c","kind":"trade","actor":{"handle":"Trader-cd1dca","display_name":"Trader-cd1dca","avatar_url":null},"market_slug":"pm-will-argentina-win-the-2026-fifa-world-cup-245","market_title":"World Cup Winner: Will Argentina win the 2026 FIFA World Cup?","headline":"YES yes 1 @ 0.1745 on pm-will-argentina-win-the-2026-fifa-world-cup-245","body":null,"created_at":"2026-07-14T00:30:14.015376Z","reactions":{"like":0},"reacted":false,"comment_count":0}],"next_cursor":"2026-07-14T00:30:14.015376Z|trade:27dac59b-b4d2-4e89-a770-b2304aec921c"}
```

```text
GET /api/v1/social/stories/{trade:27dac59b-…}/comments → 200
{"items":[]}
```

```text
GET /api/v1/social/following (anon) → 401
GET /api/v1/portfolio (anon) → 401
GET /api/v1/watchlist (anon) → 401
```

```text
GET /traders HTML (stripped text snippet)
"Public paper record Traders, with receipts See who has performed on settled paper markets..."
```

```text
GET /community HTML markers
demo-trader=False | MOCK_STORIES=False | Lakers vs Celtics=False | Community desk=True | Stories from the desk=True
```

```text
Community page chunk (honest offline copy)
"...The feed could not be loaded. Nothing fabricated is shown while the community service is offline."
"...No stories yet" / data-testid="community-empty-state"
Live fetch: /api/v1/social/stories?… (+ comments path)
```

---

## Contract conformance (Story / Comment)

### Story (`StoryOut`) — field-by-field vs live item

| field | required by contract | observed | pass? |
| --- | --- | --- | --- |
| `id` | yes | `trade:27dac59b-b4d2-4e89-a770-b2304aec921c` | PASS |
| `kind` | yes | `"trade"` | PASS |
| `actor` | yes object | present | PASS |
| `actor.handle` | yes | `"Trader-cd1dca"` | PASS |
| `actor.display_name` | yes | `"Trader-cd1dca"` | PASS |
| `actor.avatar_url` | yes (nullable) | `null` | PASS |
| `market_slug` | yes (nullable) | `"pm-will-argentina-win-the-2026-fifa-world-cup-245"` | PASS |
| `market_title` | yes (nullable) | present | PASS |
| `headline` | yes | present | PASS |
| `body` | yes (nullable) | `null` | PASS |
| `created_at` | yes | ISO-8601 Z string | PASS |
| `reactions` | yes object | `{"like":0}` | PASS |
| `reactions.like` | expected | integer `0` | PASS |
| `reacted` | yes bool | `false` (anon) | PASS |
| `comment_count` | yes int | `0` | PASS |

**Missing fields on live stories:** none of the required Story keys.  
**Extra fields on story objects:** none (keys exactly: `id,kind,actor,market_slug,market_title,headline,body,created_at,reactions,reacted,comment_count`).  
**Page envelope:** `items` + `next_cursor` only — matches `StoryPageOut`.

### Comment (`CommentOut`)

| field | evidence |
| --- | --- |
| list envelope | `{"items":[]}` on a real story id — PASS |
| `id` / `actor` / `body` / `created_at` | **UNVERIFIED** on a non-empty comment (no story in the first 75 feed items had `comment_count > 0`) |

Code/OpenAPI declare Comment as `{id, actor{handle,display_name,avatar_url}, body, created_at}`; production could only prove the empty-list path.

---

## Pagination walk

Method: `GET /api/v1/social/stories?limit=2`, then follow `next_cursor` until exhausted.

### Pages 1–3 (detail)

| page | ids | created_at (API raw / order) | next_cursor present? |
| ---: | --- | --- | --- |
| 1 | `trade:27dac59b-…`, `trade:998c90bd-…` | `2026-07-14T00:30:14…`, `2026-07-11T11:28:28.245805Z` | yes |
| 2 | `trade:2765979c-…`, `trade:3b0a4ce0-…` | **same ts** `11:28:28` as page1 tail, then `10:20:29` | yes |
| 3 | `trade:1f0deb1f-…`, `trade:db7f2d8d-…` | **same ts** `10:20:29` as page2 tail, then earlier | yes |

Timestamp collisions are present (multiple trades share identical `created_at`); cursor form `ISO|story_id` correctly continues without repeating an id.

### Full walk vs bulk page

```text
limit=2 walk to end: page=38, total=75 ids, unique=75, overlap=0
GET ?limit=100: count=75, next_cursor=null
order_mismatch vs walk: 0
missing_from_walk: 0
extra_in_walk: 0
```

**Assert:** no story id appears on two pages; walk reconstructs the full ordered feed with **no gap and no overlap**. Pre-merge cursor bug does **not** reproduce on prod data with real collisions.

---

## Regressions vs pre-deploy (GAPMAP104)

| surface | GAPMAP104 | PRODSMOKE104 | regression? |
| --- | --- | --- | --- |
| `/health` paper flag | `paper_trading_only:true` | same | no |
| `/api/v1/markets` size/latency | ~2.3MB / ~2278ms | ~2.35MB / ~1702ms | no (still large; improved slightly this sample) |
| signals/dashboard | 200 non-empty | 200 ~42KB | no |
| home / feed / screener | 200 with data | 200 with data | no |
| leaderboard | 200, **1** entry | 200, **1** entry (`Trader-cd1dca`) | no |
| track-record / Brier | live data | `n:200`, brier≈0.070 | no |
| alpha/report hollow factors | `valid:false`, missing_closing_line | same pattern | **pre-existing**, not wave-104 empty regression |
| `/traders` frontend | EXCLUDED / dead workstream (0-byte 404 historically) | **200 + real SSR** | **fixed by ship** |
| social stories API | not in GAPMAP public curls | **200 live derived feed (75 stories)** | new, healthy |

**Loud regression criteria (5xx or previously-full → empty):** none met.

Latency flags (&gt;~3s): **none** on this pass (markets ~1.7s was the slowest required surface).

---

## Paper-guardrail + truthfulness findings

### Paper guardrail

- `/health`: **`paper_trading_only: true`** + simulation disclaimer (fragment above).
- Signals dashboard carries paper disclaimer in payload.
- Trader profile: `"paper_trading_only":true`.
- Frontend `/community` and `/trade` HTML: paper-trading simulation / simulated funds present; **no** `real money`, `deposit`, `withdraw`, or funding-rail copy found in HTML.
- Site chrome includes **Sim** labeling (SSR snippets).
- OpenAPI info description still frames paper-trading simulation.

### Truthfulness (community feed)

| check | result |
| --- | --- |
| SSR HTML contains `demo-trader` | **False** |
| SSR HTML contains `Lakers vs Celtics` as page copy | **False** |
| SSR HTML contains `MOCK_STORIES` | **False** |
| Community page JS contains `MOCK_STORIES` | **False (0 matches)** |
| Community page JS offline behavior | Explicit: *“Nothing fabricated is shown while the community service is offline.”* |
| Community page empty state | *“No stories yet”* / `community-empty-state` |
| Client data source | Live `GET /api/v1/social/stories` (+ comments URL) |
| API stories | Derived real trades (`trade:<uuid>`), handles like `Trader-cd1dca` matching leaderboard |

**Note on `Lakers vs Celtics` in API:** several **real** derived trade stories reference market slug `nba-2025-01-15-lal-bos` with title `Lakers vs Celtics` (canonical paper test market). That is production paper-trade data, **not** the deleted client fixture list. It does **not** appear fabricated into `/community` HTML.

**Note on `demo-trader-*` strings in shared chunk `3861-*.js`:** array `demo-trader-1`…`demo-trader-12` still ships in a **shared** frontend chunk (avatar/color helper style usage). **Not** referenced from community page HTML as story actors; community feed path uses live API handles. Flagged as residual demo-handle vocabulary in a shared bundle — **not** a community fabricate-on-failure regression.

---

## Anonymous safety

| check | result |
| --- | --- |
| `reacted` on anon stories | **All false** on default page (0/20 `reacted:true`); pages 1–3 of limit=2 walk also all `false` |
| USER-auth GET without token | `/api/v1/social/following` → **401**; `/api/v1/portfolio` → **401**; `/api/v1/watchlist` → **401** |
| Mutation auth | **GET-only policy:** did **not** POST reactions/comments. |

### OpenAPI / docs auth class

From live `GET /openapi.json`:

| operation | OpenAPI `security` |
| --- | --- |
| `GET /api/v1/social/stories` | `HTTPBearer` listed (runtime allows anonymous; optional viewer) |
| `GET /api/v1/social/stories/{id}/comments` | `security: null` (public) |
| `POST …/comments` | `HTTPBearer` |
| `POST …/reactions` | `HTTPBearer` |
| `DELETE …/reactions/like` | `HTTPBearer` |
| `GET /api/v1/social/following` | `HTTPBearer` |
| Scheme | `HTTPBearer` → `type: http`, `scheme: bearer` |

OpenAPI **does not document 401 response bodies** for these ops (`responses` for POST comments list only `200,422`), but runtime GET of following correctly returns **401** without a bearer token.  
**POST auth enforcement:** documented as bearer-required; **runtime 401/403 on POST not exercised** (GET-only rule) → see UNVERIFIED.

---

## UNVERIFIED

1. **Non-empty Comment object shape in production** — no story with `comment_count > 0` in the 75-item feed; only `{"items":[]}` proven.
2. **POST/DELETE auth runtime** for reactions/comments — not probed (no mutations allowed). OpenAPI marks `HTTPBearer`; treat runtime gate as **documented, not re-proven**.
3. **Browser-hydrated community DOM** after client fetch (Playwright/headless not used). Proven: SSR has no fixtures; API returns real stories; client chunk wires live API + honest empty/error. Pixel-level “cards visible” **UNVERIFIED**.
4. **`/w/[handle]` success path with a real shared handle** — only `demo` tried (404 API, 200 page shell).
5. **Whether optional `HTTPBearer` on GET stories changes `reacted` for an authenticated viewer** — needs user JWT → **NEEDS USER: session/JWT** if that must be proven.
6. **CORS / cookie session specifics** for frontend→API from browser origin — not exercised beyond public GETs from this runner.

---

## Method

- Tooling: PowerShell `Invoke-WebRequest` GET only against prod API + Vercel frontend; OpenAPI snapshot from prod `/openapi.json`.
- Retries: no hard transport failures requiring the 2-retry budget; 401/404 treated as successful contract responses.
- AutoLab: not applicable (one-shot post-deploy verify, no iterative measure).

**End of PRODSMOKE104.**
