# Loop V3 — Surface the shipped intelligence + one aggregate (2026-07-10)

> Two parallel tracks in isolated worktrees. Orchestrator (Claude, main
> thread) reviews, merges, gates, deploys. One ticket per iteration per track.

## WHY (grounded)

Backend already ships cross-venue arb matching (G02), a track-record aggregate
(G05: calibration bins + Brier-over-time + CLV), and a smart-money endpoint
(G07) — but NONE has a dedicated frontend page, so the intelligence is
invisible. Research says discoverability + transparency beat new features.
Loop V3 surfaces what exists and adds one aggregate endpoint to cut request
flooding.

## GROUND TRUTH

- Prod backend https://mukeshkumar007-alphaedge-api.hf.space (auto-deploy on
  push to codex/alphaedge-base). Prod frontend
  https://alphaedge-frontend-three.vercel.app (cd frontend && npx vercel
  --prod --yes). verify_prod.py = 6/6.
- Existing contracts to consume (see goals/loop-grok-backend/API-NOTES.md):
  GET /api/v1/track-record, GET /api/v1/smart-money?slug=&hours=&top_n=,
  GET /api/v1/arb/opportunities (confidence/spread_bps/legs/stale),
  GET /api/v1/calibration/latest, GET /api/v1/search.

## GATE (per track, before any ticket DONE — paste output)

- Frontend (from frontend/): `npm run typecheck && npm run lint &&
  npm run test -- --run && npm run build`. UI tickets: reason about 390px
  no-overflow; Quest tokens only.
- Backend (from backend/): `uv run --extra dev pytest -q` (set
  ADMIN_API_KEY=dev-admin-key) and `uv run --extra dev ruff check app tests`.

## GUARDRAILS (non-negotiable)

- PAPER_TRADING_ONLY; all new surfaces ANALYSIS ONLY (signal_only /
  paper_trading_only). Order path untouched (RiskService → OrderIntent →
  OrderBookService). No auto-trading of arb/smart-money.
- No fabricated data; honest empty/thin-data states (respect track-record
  `thin_data`, arb empty reasons, smart-money empty). Never weaken a test.
- Frontend track edits ONLY frontend/** + goals/loop-v3/**. Backend track
  edits ONLY backend/** + goals/loop-v3/**. Additive API only; document new
  contracts in goals/loop-v3/API-NOTES.md.
- Quest design language (tailwind tokens + globals.css vars) only.

## FRONTEND TRACK (worktree loop-opus-polish)

- **F01 — Public Track Record page** `/track-record` consuming
  GET /api/v1/track-record: calibration reliability curve (predicted vs
  observed bins), Brier-over-time line, CLV distribution histogram, resolved
  count `n` with a prominent "provisional (n=X)" caveat when `thin_data`.
  Honest empty when source=="none". Nav link under More. THE transparency
  differentiator. Vitest for the view-model.
- **F02 — Smart Money page** `/smart-money` consuming
  GET /api/v1/smart-money: top holders, whale concentration, recent large
  flows, trade-intensity sparkline; market picker (reuse search/markets).
  Read-only + "paper-trade this market" CTA to the trade panel. Honest empty.
  Nav + Discover Intelligence link. Vitest.
- **F03 — Cross-venue arb view** `/arb` (or a dedicated tab on /signals):
  matched Polymarket↔Kalshi pairs from GET /api/v1/arb/opportunities with
  per-leg breakdown, confidence + spread_bps chips, stale flag; reasoned empty
  ("no matched pair / below confidence / stale"). Reuse arb-api.ts. signal
  only.
- **F04 — Evidence on signal cards**: for `news:mispricing` show the news
  headline + source link + model-vs-market edge; for `anomaly:unusual_flow`
  show the neutral "no public catalyst found" note. Deepen P05 feed/signals.
- **F05 — First-bet onboarding**: 3-step guided flow on first visit (what a
  price means; what our edge/signals mean; place a paper trade on a suggested
  liquid market). localStorage dismissal; reuse Quest onboarding components.
  E2E or vitest for the flow.
- **F06 — Motion pass** on new pages + core surfaces: scroll reveals,
  animated number transitions on prices/edges, skeletons on data load,
  `prefers-reduced-motion` respected. Quest tokens; no perf regression.

## BACKEND TRACK (worktree loop-grok-backend)

- **H01 — Single-market desk aggregate** `GET /api/v1/desk?slug=`: compose
  market snapshot + latest model-vs-market edge + smart-money summary (G07) +
  arb match if any (G02) + latest signals for the slug, in ONE response, so
  the market page renders its intelligence panel with one call (cuts request
  flooding). Additive, read-only, composition of existing services only.
  Tests with fixtures. Document JSON in goals/loop-v3/API-NOTES.md.
- **H02 — Backtest summary endpoint** `GET /api/v1/backtest/summary`:
  walk-forward Brier + ROI over resolved external markets (reuse the
  resolution sources used by track-record/G06; jon-becker dataset schema as
  idea only). Include `n` + `thin_data`. Read-only, tests.
- **H03 — Signal citation consistency**: ensure `news:mispricing` and
  `anomaly:unusual_flow` payloads carry stable ids + consistent citation
  fields (news_id/news_url/headline, model_p/market_p) so F04 can rely on
  them; add a schema/contract test. No new pipeline.

## ITERATION PROTOCOL (per track)

1. git status (confirm correct worktree/branch). Name the ticket.
2. Smallest green slice; reuse existing modules; Quest tokens.
3. Run the track GATE; fix until green.
4. Update LOOP LOG + API-NOTES.md (backend) with evidence + AutoLab line;
   commit `feat(v3-fe|v3-be): <ticket> <summary>`. Do NOT push. STOP.

## LOOP LOG

| iter | date | track | ticket | result | proof |
|------|------|-------|--------|--------|-------|
| 3 | 2026-07-10 | FE | F03 | DONE | New dedicated `/arb` cross-venue monitor reuses `arb-api.ts` `fetchArbOpportunities`: matched-pairs/fresh/stale stat tiles, per-card Edge/Spread(bps)/Conf chips, per-leg breakdown table (venue · leg · price · fee), fresh/stale badge, reasoned empty via new exported pure `arbEmptyReason` (no matched pair / all-stale / below-bar / backend-unreached). Signal-only framing throughout; PM/Kalshi market links. Added `arbEmptyReason` + 4 unit tests; `/signals` links to the full monitor. Nav: added "Arb" to HeaderMoreMenu. Gate: typecheck ✓ lint ✓ vitest 131/131 ✓ (4 new tests) build ✓ (/arb 3.46 kB). AutoLab: baseline=arb only a compact /signals card | benchmark=dedicated page with per-leg breakdown + confidence/spread chips + reasoned empty | iterations=1 (green first pass) | budget=1/1 | outcome=improved. |
| 2 | 2026-07-10 | FE | F02 | DONE | New `/smart-money` desk consumes G07 `GET /api/v1/smart-money?slug=&hours=&top_n=` via new `lib/smart-money-api.ts` (`fetchSmartMoney` + pure `buildSmartMoneyView`): whale-concentration + tracked-size + depth-skew + fills/hour stat tiles, trade-intensity magnitude bar, recent large-flows list (truncated wallets, buy/sell toned), honest empty when `market_found=false`. Market picker reuses shared `fetchMarkets` cache (top-6 by volume quick-picks) + `searchUnified` typeahead. Read-only + "Paper-trade this market" CTA → `/trade?slug=`. 6/24/72h window toggle. Nav: added to HeaderMoreMenu MORE_NAV + Discover Intelligence links (QuestDiscoverShell). DEGRADE NOTE: G07 returns a single trade-intensity aggregate (no per-bucket series), so a true sparkline isn't in the contract — rendered a magnitude bar instead (INTENSITY_REF=20 fills/hr cap), not fabricated series. Gate: typecheck ✓ lint ✓ vitest 127/127 ✓ (7 new view-model tests) build ✓ (/smart-money 4.88 kB). AutoLab: baseline=G07 endpoint shipped, no FE surface | benchmark=page renders real whale/flow/intensity + honest empty + CTA | iterations=1 (fixed 1 toFixed rounding expectation in test) | budget=1/1 | outcome=improved. |
| 1 | 2026-07-10 | FE | F01 | DONE | `/track-record` now consumes G05 `GET /api/v1/track-record` via new `lib/track-record-api.ts` (`fetchPublicTrackRecord` + pure `buildTrackRecordView`) rendered by new `components/TrackRecordReliability.tsx`: reliability curve (predicted vs observed, filled bins only, sized by count), cumulative-Brier line, CLV histogram, `n=` + Brier + mean-CLV stat tiles, prominent gold "Provisional (n=X)" caveat when `thin_data`, honest empty when `source==="none"`. Nav link already under More (HeaderMoreMenu "Track record"). Charts are inline SVG using text-token classes (`fill-primary`/`stroke-accent`), CLV bars horizontal for 390px no-overflow. Gate: typecheck ✓ lint ✓ vitest 120/120 ✓ (10 new view-model tests) build ✓ (/track-record 5.35 kB). AutoLab: baseline=G05 endpoint shipped but no FE surface (intelligence invisible) | benchmark=page renders real reliability/Brier/CLV + thin-data caveat + honest empty | iterations=1 (green first pass) | budget=1/1 | outcome=improved. |
