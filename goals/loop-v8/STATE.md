# Loop V8 — Personalized home + shareable intelligence (2026-07-10)

> SEQUENTIAL execution. Backend track completes FIRST, merges + gates, THEN
> the frontend track. Orchestrator (Claude, main thread) reviews, merges,
> gates, deploys, verifies. One commit per ticket (commit each ticket the
> moment its gate is green — do not batch).
>
> ORCHESTRATOR NOTE: V8 backend may build while V7 finishes deploying, but V8
> is only merged into loop3-agent-memory AFTER V7 is deployed + verified 6/6,
> so each loop ships as its own clean release.

## WHY (grounded)

V1-V7 built the intelligence, surfaced it, made it personal (watchlist,
alerts, prefs) and tunable (backtest params, digest). What's missing is a
single PERSONALIZED landing that pulls it together, and a way to SHARE a
market's read-only intelligence. Plus the free-tier Space needs caching on the
new heavy read paths. All in-app, no external rails.

## GROUND TRUTH

- Prod backend https://mukeshkumar007-alphaedge-api.hf.space (auto-deploy on
  push to codex/alphaedge-base); prod frontend
  https://alphaedge-frontend-three.vercel.app (cd frontend && npx vercel
  --prod --yes). verify_prod.py = 6/6 through V7.
- Contracts shipped: v3-v7 API-NOTES.md — desk, track-record, backtest
  summary+run, smart-money, arb, signals, resolved-count, model-ab,
  watchlist, alerts feed+digest, notify prefs. Reuse desk_cache.py pattern,
  the JWT dep, the I01 5xx guard.

## GATE (per track — paste output in LOOP LOG)

- Backend (backend/): `ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest
  -q -p no:cacheprovider --basetemp=<scratchpad>` and
  `uv run --extra dev ruff check app tests`.
- Frontend (frontend/): `npm run typecheck && npm run lint &&
  npm run test -- --run && npm run build`. 390px no-overflow; Quest tokens.

## GUARDRAILS (non-negotiable)

- PAPER_TRADING_ONLY; analysis/notify-only; order path untouched; no
  auto-trading; no external delivery/rails; snapshots persist nothing.
- No fabricated data; honest empty/thin-data states. Never weaken a test.
- New PUBLIC GET routes stay covered by the I01 5xx guard. Authed enrichment
  degrades gracefully for anon. Additive API only; document in
  goals/loop-v8/API-NOTES.md.
- Backend edits ONLY backend/** + goals/loop-v8/**; frontend ONLY
  frontend/** + goals/loop-v8/**. Quest design language only.

## BACKEND TRACK (worktree loop-grok-backend) — RUNS FIRST

- **M01 — Personalized home aggregate**: `GET /api/v1/home` — ONE call that
  composes, from existing services: top N recent signals (with H03
  citations), the alerts digest summary (L02), model-A/B status (J03/I02
  resolved-count), and top markets by liquidity. When authed (JWT optional on
  this route), ALSO include the caller's watchlist count + recent
  watchlist alerts (K03). Public/anon returns the non-personal sections only.
  Read-only composition; honest empties. In the I01 sweep. Tests: anon shape,
  authed enrichment, honest empty.
- **M02 — Shareable market snapshot**: `GET /api/v1/markets/{slug}/snapshot`
  (PUBLIC GET) — a compact read-only intelligence snapshot for one market:
  title, current YES price, model-vs-market edge one-liner, top signal, arb
  match flag, smart-money one-liner. Small + cacheable (reuse the desk_cache
  TTL pattern; include `cached: bool`). Unknown slug → honest 200
  {found:false}. In the I01 sweep. Tests: known slug, unknown honest, cache
  hit/expiry.
- **M03 — ETag/304 on heavy public GETs**: add weak-ETag + If-None-Match →
  304 support to `/home`, `/markets/{slug}/snapshot`, and `/backtest/summary`
  (additive response headers only; body unchanged on 200). Cuts free-tier
  egress. Tests: 200 sets ETag, matching If-None-Match → 304 no body,
  changed data → new ETag.

## FRONTEND TRACK (worktree loop-opus-polish) — RUNS AFTER V7 DEPLOY + BACKEND MERGE

- **Z01 — Personalized home dashboard**: a `/home` (or enhance the root)
  surface consuming `GET /api/v1/home`: "your intelligence" sections — top
  signals, digest summary, model status, top markets; when authed also the
  watchlist strip. Honest anon ("sign in to personalize") + empty states.
  Reuse SignalEvidence/AnimatedNumber/AlertsDigest card. Vitest for the
  view-model. Add to nav.
- **Z02 — Shareable snapshot page**: a `/s/[slug]` read-only share page
  consuming `GET /api/v1/markets/{slug}/snapshot`: a clean snapshot card
  (price, edge, top signal, smart-money one-liner) with a "view full market"
  link and a copy-link button. Honest not-found. Quest tokens. Vitest.
- **Z03 — Wire-in + a11y + perf closeout**: link Home from the header/nav and
  a "Share" affordance from the market detail desk panel to /s/[slug];
  skeletons, AnimatedNumber, reduced-motion, 390px no-overflow, aria-labels
  on the new surfaces. Log findings honestly.

## ITERATION PROTOCOL (per track)

1. git status (confirm worktree/branch). Name the ticket.
2. Smallest green slice; reuse existing modules/components.
3. Run the track GATE; fix until green.
4. Update LOOP LOG (+ API-NOTES.md for backend) with evidence + AutoLab
   line; commit `feat(v8-be|v8-fe): <ticket> <summary>` immediately. No push.

## LOOP LOG

| iter | date | track | ticket | result | proof |
|------|------|-------|--------|--------|-------|
| 1 | 2026-07-10 | BE | M01 | done | `GET /api/v1/home` personalized aggregate (signals+H03 citations, L02 digest, model-A/B readiness, top markets; authed watchlist enrichment). test_home_api.py 3/3 + I01 guard; full: 1261 passed, 28 skipped; ruff clean. AutoLab: not applicable (no iterative measure) — one-shot additive read-only composition. |
| 2 | 2026-07-10 | BE | M02 | done | `GET /api/v1/markets/{slug}/share-snapshot` compact shareable snapshot (title, yes_price, edge one-liner, top_signal+citation, arb flag, smart_money_note; snapshot_cache TTL + `cached` flag). Path chosen to avoid collision with the locked full `/snapshot`. test_market_share_snapshot_api.py 4/4 + I01 guard; full: 1265 passed, 28 skipped; ruff clean. AutoLab: not applicable (no iterative measure). |
| 3 | 2026-07-10 | BE | M03 | done | Weak-ETag + `If-None-Match`→304 on `/home`, `/markets/{slug}/share-snapshot`, `/backtest/summary` via `app/core/http_etag.py` (clock-derived keys generated_at/since/cached stripped so validator tracks content; 200 body unchanged). test_etag_conditional_get.py 7/7 (helper + 3 routes); full: 1271 passed, 28 skipped; ruff clean. AutoLab: not applicable (no iterative measure). |
| 4 | 2026-07-10 | FE | Z01 | done | `/home` personalized dashboard consuming `GET /api/v1/home` — top signals (F04 SignalEvidenceBlock), compact L02 digest summary, I02/J03 model-A/B readiness progress, top-markets-by-liquidity; authed watchlist strip (count + K03 watchlist alerts), anon "sign in to personalize" for that section only. New `lib/home-api.ts` (pure `buildHomeView`/`buildSignalRows`/`buildMarketRows`, reuses digest/model-ab/alerts builders + fetchHome with optional Bearer). "Home" added to header nav. Skeletons + AnimatedNumber + MotionReveal + honest empties; 390px single-column, min-w-0/truncate/flex-wrap → no overflow. Gate: typecheck ✓, lint ✓ (0 warnings), vitest 243 passed (42 files; home-api 8/8), build ✓ (/home 7.48 kB). AutoLab: not applicable (no iterative measure) — additive read-only surface. |
| 5 | 2026-07-10 | FE | Z02 | done | `/s/[slug]` read-only shareable snapshot consuming `GET /api/v1/markets/{slug}/share-snapshot` (the M02 compact path, NOT the locked full `/snapshot`). Clean card: title, YES price, model-vs-market edge one-liner, smart-money one-liner, cross-venue arb flag, top signal with H03 evidence; "View full market →" (marketHref) + "Copy link" (copies the /s/[slug] URL, Copied✓ state). Honest unreachable / {found:false} not-found states. New `lib/share-snapshot-api.ts` (pure `buildShareSnapshotView` + fetchShareSnapshot). Server page + client, generateStaticParams over seed catalog + dynamicParams for live slugs. Quest tokens, MotionReveal, AnimatedNumber-free price (static) but tokenized; narrow shell max-w-2xl → 390px safe (flex-wrap edge line). Gate: typecheck ✓, lint ✓ (0 warnings), vitest 247 passed (43 files; share-snapshot 4/4), build ✓ (/s/[slug] 4.2 kB SSG). AutoLab: not applicable (no iterative measure). |
