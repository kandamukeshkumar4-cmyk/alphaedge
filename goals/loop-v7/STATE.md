# Loop V7 — Tunable strategy backtest, alerts digest, notify prefs (2026-07-10)

> SEQUENTIAL execution (V5 lesson). Backend track completes FIRST, merges +
> gates, THEN the frontend track. Orchestrator (Claude, main thread) reviews,
> merges, gates, deploys to prod, verifies. One commit per ticket.

## WHY (grounded)

V6 gave users a self-serve backtest, portfolio CLV, and watchlist alerts. The
next step is making it TUNABLE and DIGESTIBLE: run a backtest with your own
edge/stake assumptions, get a digest of what your alerts mean over a window,
and choose which alert families you care about. All in-app — NO external
send (email/SMS/webhook) which would breach the no-external-rails guardrail.

## GROUND TRUTH

- Prod backend https://mukeshkumar007-alphaedge-api.hf.space (auto-deploy on
  push to codex/alphaedge-base); prod frontend
  https://alphaedge-frontend-three.vercel.app (cd frontend && npx vercel
  --prod --yes). verify_prod.py = 6/6, all V1-V6 endpoints 200 as of
  2026-07-10.
- Contracts shipped: v3-v6 API-NOTES.md. Reuse backtesting/replay + the
  /backtest/run K01 code, the alerts feed (alerts_feed.py), the JWT dep,
  the watchlist store, and the I01 5xx guard.

## GATE (per track — paste output in LOOP LOG)

- Backend (backend/): `ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest
  -q -p no:cacheprovider --basetemp=<scratchpad>` and
  `uv run --extra dev ruff check app tests`.
- Frontend (frontend/): `npm run typecheck && npm run lint &&
  npm run test -- --run && npm run build`. 390px no-overflow; Quest tokens.

## GUARDRAILS (non-negotiable)

- PAPER_TRADING_ONLY; analysis/notify-only; order path untouched; no
  auto-trading; backtests persist nothing and place no orders; NO external
  notification delivery (prefs are stored + read in-app only).
- No fabricated data; honest empty/thin-data states. Never weaken a test.
- New PUBLIC GET routes stay covered by the I01 5xx guard. Authed routes 401
  when anon. Additive API only; document in goals/loop-v7/API-NOTES.md.
- Backend edits ONLY backend/** + goals/loop-v7/**; frontend ONLY
  frontend/** + goals/loop-v7/**. Quest design language only.

## BACKEND TRACK (worktree loop-grok-backend) — RUNS FIRST

- **L01 — Parametrized self-serve backtest**: extend `GET /api/v1/backtest/run`
  with OPTIONAL query params `edge_threshold` (min model-vs-market edge to
  place a paper bet, default current behavior) and `stake` (flat stake size,
  default 1.0). Deterministic, read-only; params clamp to sane ranges;
  omitting them reproduces K01 exactly (regression test). Honest {ran:false}
  path unchanged; still in the I01 sweep. Tests: default==K01, threshold
  filters bets, stake scales pnl, out-of-range clamps.
- **L02 — Alerts digest**: `GET /api/v1/alerts/digest?window=24h&slugs=`
  (PUBLIC GET) → counts per family (news:mispricing / anomaly:unusual_flow /
  delta:* / screener:* / arb) + top-N moved markets in the window, from the
  existing signal store. Honest empty. Keep in the I01 sweep. Tests:
  family counts, window filter, honest empty, top-movers ordering.
- **L03 — Notification preferences store**: `GET /api/v1/notify/prefs` +
  `PUT /api/v1/notify/prefs` (authed via JWT) → per-user opt-in set of alert
  families (stored only — NO external delivery). New table via Alembic
  migration chaining from the single head (036). Sensible default (all on).
  401 anon. Tests: default on first read, PUT round-trips, invalid family
  rejected, per-user isolation.

## FRONTEND TRACK (worktree loop-opus-polish) — RUNS AFTER BACKEND MERGES

- **Y01 — Strategy params on the backtest UI**: on the self-serve backtest
  (/backtest), add edge-threshold + stake inputs that re-run
  `GET /api/v1/backtest/run?slug=&edge_threshold=&stake=` and show how the
  per-market Brier/ROI responds; honest states unchanged. Reuse the X01
  backtest-run view-model. Vitest.
- **Y02 — Alerts digest card**: on /alerts, a digest summary (consume L02):
  per-family counts + top movers over a window toggle (24h/7d), honest empty.
  Reuse SignalEvidence family labels. Vitest.
- **Y03 — Notification preferences UI**: a prefs panel (on /alerts or a
  settings surface) consuming L03 (authed GET/PUT): toggle which alert
  families surface; the header bell + /alerts default-filter respect the
  stored prefs; honest anon ("sign in"). Optimistic PUT. Vitest.
- **Y04 — Consistency + a11y closeout** on the new V7 surfaces: skeletons,
  AnimatedNumber, reduced-motion, 390px no-overflow, aria-labels; log
  findings honestly.

## ITERATION PROTOCOL (per track)

1. git status (confirm worktree/branch). Name the ticket.
2. Smallest green slice; reuse existing modules/components.
3. Run the track GATE; fix until green.
4. Update LOOP LOG (+ API-NOTES.md for backend) with evidence + AutoLab
   line; commit `feat(v7-be|v7-fe): <ticket> <summary>`. Do NOT push. STOP.

## LOOP LOG

| iter | date | track | ticket | result | proof |
|------|------|-------|--------|--------|-------|
| 1 | 2026-07-10 | BE | L01 | green | pytest 10 passed (backtest_run_slug + 5xx guard), ruff clean. edge_threshold+stake OPTIONAL params, clamped, default==K01 byte-for-byte. AutoLab: baseline=K01 green | benchmark=test_default_params_reproduce_k01_byte_for_byte | iterations=1 (params additive, no perturbation) | budget=1/3 | outcome=improved |
| 2 | 2026-07-10 | BE | L02 | green | pytest 14 passed (digest + feed + 5xx guard), ruff clean. New PUBLIC GET /alerts/digest: per-family counts + top-movers over bounded window, honest empty, added to 5xx MUST_COVER. AutoLab: baseline=L01 green | benchmark=test_family_counts_and_window + top_movers ordering | iterations=2 (fixed window canonical 24h vs 1d) | budget=2/3 | outcome=improved |
| 3 | 2026-07-10 | BE | L03 | green | pytest 9 passed (notify_prefs + 5xx guard); full suite + ruff green. Authed GET/PUT /notify/prefs, new table notify_prefs (Alembic 036_notify_prefs, single head), default-all-on, 422 invalid family, per-user isolation, 401 anon. STORED only — no external delivery. AutoLab: baseline=L02 green | benchmark=notify_prefs round-trip + isolation tests | iterations=1 | budget=1/3 | outcome=improved |
| 4 | 2026-07-10 | FE | Y01 | green | typecheck+lint clean, vitest 213 passed (39 files; +5 new buildBacktestRunQuery cases in backtest-run-api.test.ts), build OK. SelfServeBacktest gains edge_threshold + stake inputs that debounce-rerun GET /backtest/run?slug=&edge_threshold=&stake= via a param-aware effect (abort on change, no poll loop); honest caption that Brier is invariant to params (only n_bets/P&L/ROI respond, ROI stake-invariant); empty inputs reproduce K01 default byte-for-byte; out-of-range clamps client-side too. 390px: params row is flex-wrap basis-40 min-w-0 → stacks, no overflow. AutoLab: baseline=X01 backtest view green | benchmark=buildBacktestRunQuery default==K01 + clamp cases | iterations=1 (additive params) | budget=1/3 | outcome=improved |
| 5 | 2026-07-10 | FE | Y02 | green | typecheck+lint clean, vitest 223 passed (40 files; +10 new alerts-digest-api.test.ts), build OK. New lib alerts-digest-api.ts (pure buildAlertsDigestView + fetchAlertsDigest) consuming GET /alerts/digest?window=&top=; new AlertsDigest card on /alerts with 24h/7d aria-labelled toggle, per-family counts (canonical-ordered, AnimatedNumber), top-movers (marketHref links), honest empty + unreachable. Family labels reuse the SignalEvidence vocabulary (News/Flow/Screener) + honest names for delta:*/arb. 390px: family pills flex-wrap; mover rows flex with min-w-0 truncate slug + shrink-0 badges, family/time badges sm:inline only → no overflow. AutoLab: baseline=W02 alerts feed green | benchmark=buildAlertsDigestView sort/empty/mover-order cases | iterations=1 | budget=1/3 | outcome=improved |
