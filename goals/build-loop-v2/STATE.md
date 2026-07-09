# Build Loop v2 — Intelligence Depth + Questflow Polish (2026-07-09)

> Executor: any capable coding agent (Cursor / Grok 4.5 / Claude / Codex).
> Read this file FIRST, fully, plus `AGENTS.md` and `CLAUDE.md`. Do exactly
> ONE ticket per iteration, then stop.

## WHY THIS LOOP (research-grounded, 2026-07-09)

Last-30-days community research (r/PredictionMarkets, r/Polymarket,
r/algotrading, GitHub, news) says the winning tool categories right now are:

1. **Cross-venue aggregation + arb** (Oddpool, PredictOS) — traders want one
   dashboard across Polymarket + Kalshi with matched-market spreads.
2. **AI research/forecast agents with evidence** (Polybro, FutureShow,
   Kalshi News Bot: news → mispriced event → signal) — the hot pattern is
   "structured research → evidence-based edge", not black-box picks.
3. **Whale tracking / smart-money / copy-trading surfaces** (PredictOS).
4. **Trust & transparency** — Congress insider-trading probe (80+ suspicious
   pre-news bets) dominates the news; a public, honest track record
   (calibration, CLV, Brier) is a differentiator nobody in the niche shows.
5. Newcomers ask "what should I learn before my first bet?" — education /
   explainability surfaces convert them.

Reference repos (ideas only, clean-room; NEVER copy code without checking
license): `aarora4/Awesome-Prediction-Market-Tools`, `PredictionXBT/PredictOS`,
`HKUDS/FutureShow`, `gnosis/prediction-market-agent`, `py-clob-client`.

## GROUND TRUTH (verified 2026-07-09)

- Prod backend: https://mukeshkumar007-alphaedge-api.hf.space (HF Space,
  auto-deploys on push to `codex/alphaedge-base`).
- Prod frontend: https://alphaedge-frontend-three.vercel.app (deploy with
  `cd frontend && npx vercel --prod --yes`).
- `py -3.13 scripts/verify_prod.py` = 6/6 PASS. All prior loops DONE
  (see `goals/e2e-ship/STATE.md`). Prod admin key works; memories seeded.
- Existing assets to REUSE (do not rebuild): signals pipeline + scheduler,
  news_signal node, `arb-api.ts` + Cross-market arb panel (currently empty),
  analyst tools (`get_order_book_summary/get_price_history/get_whale_activity/
  get_depth_skew/get_whale_concentration/get_trade_intensity`), agent
  memories, CLV tracking, leaderboard, Quest design system.

## GATE (run FULL gate before marking any ticket DONE — paste output)

- Backend (from `backend/`): `uv run --extra dev pytest -q` AND
  `uv run --extra dev ruff check app tests`
- Frontend (from `frontend/`): `npm run typecheck && npm run lint &&
  npm run test -- --run && npm run build`
- Orchestration gate: `py -3.13 orchestration/gate.py` exit 0
- If the ticket touches deploy-affecting code and you deploy:
  `py -3.13 scripts/verify_prod.py` 6/6 against production.
- UI tickets: render the page in a browser (or Playwright) and paste evidence.

## GUARDRAILS (non-negotiable, from AGENTS.md)

- PAPER_TRADING_ONLY stays true everywhere. No cash/payment/execution language.
- Order path untouched: RiskService → OrderIntent → OrderBookService only.
  LLM/agent code never submits raw orders. No auto-execution of arb/copy ideas
  — surfaces are ANALYSIS ONLY with a paper-trade CTA.
- No fabricated data or metrics. Empty states stay honest ("no arb right now").
  Demo fixtures only behind DemoChip when the API is empty.
- No AGPL code (FinceptTerminal etc.). Check licenses before borrowing ideas.
- UI stays in the Quest design language (tailwind.config.ts tokens +
  globals.css CSS vars). Do not invent a new visual system.
- Never weaken a test/guardrail to pass the gate. 3 failed attempts at one
  error → write `orchestration/ESCALATION.md` and stop.
- Commit per ticket: `feat(loop-v2): <ticket-id> <summary>` + AutoLab line in
  body. Push only `codex/alphaedge-base`-safe work per repo workflow; ask the
  owner before pushing anything deploy-affecting if unsure.

## TICKETS (do in order; one per iteration)

### V2-T1 — Matched-market cross-venue arb engine (TODO)
The arb panel exists but is always empty because nothing matches Polymarket ↔
Kalshi markets. Backend: build a matcher (title/entity/date fuzzy match with a
confidence score) between `pm-` and `ks-` markets; compute spread = |pm_yes −
ks_yes| net of fee assumptions; expose via existing arb endpoint with
`confidence`, `spread_bps`, `legs`. Persist matches so they're stable. Tests
for the matcher (incl. false-positive guard: different strike dates never
match). Frontend: arb panel shows legs, spread, confidence chip; honest empty
otherwise. AutoLab benchmark: number of correct matches on a hand-labelled
fixture set of 20 pairs (target ≥16/20, zero false positives).

### V2-T2 — Smart Money page (whale tracking surface) (TODO)
New `/smart-money` Quest page fed by existing whale tools/endpoints: top
holders per market, whale concentration, recent large flows, trade intensity
sparkline. Read-only analysis; "paper-trade this market" CTA links to the
existing trade panel. Add to nav + Discover Intelligence links. Honest empty
when whale data absent. Vitest for components; Playwright render check.

### V2-T3 — News→Mispricing signal (Kalshi-News-Bot pattern) (TODO)
We already ingest news (news_signal node) and have model probabilities. Add a
signal type `news:mispricing`: when a fresh news item moves the model's p but
market price hasn't moved (|model_p − market_p| ≥ threshold within N minutes
of news timestamp), emit a signal citing the news item. Backend tests with
fixture news+prices. Surface in /signals feed with the news citation and
model-vs-market edge. Never auto-trades.

### V2-T4 — Public Track Record / calibration page (TODO)
Trust differentiator. New `/track-record` page: calibration curve (predicted
p vs realized frequency buckets), Brier score over time, CLV distribution,
resolved-market count — all from REAL resolved data (memories/resolutions).
With ~few resolutions, show honest "n=X, statistically thin" caveat. Backend:
one aggregate endpoint with tests. This also sets up owner-action #4
(LightGBM A/B at ~100 resolutions).

### V2-T5 — Unusual-activity detector (insider-anomaly signal) (TODO)
Topical (Congress probe). Signal type `anomaly:unusual_flow`: price jump or
volume spike with NO matching news item in the window (inverse of V2-T3).
Label it "Unusual activity — no public catalyst found". Backend tests with
fixtures. Surface in /signals with honest wording (no accusations).

### V2-T6 — Questflow-grade motion pass on core surfaces (TODO)
UI polish only, no data changes: scroll-reveals and staggered entrances on
Discover/Signals/Smart Money cards, animated number transitions on prices and
edges, smooth chart crosshair/tooltip, skeletons everywhere data loads,
respect `prefers-reduced-motion`. Stay in Quest tokens. Verify: no horizontal
overflow at 390px, Lighthouse perf not degraded (paste before/after), build
green. Use IntersectionObserver patterns already in the codebase.

### V2-T7 — First-bet onboarding / explainability (TODO)
For the "what should I learn before my first bet?" crowd: a lightweight
guided flow on first visit (3 steps: what a price means, what our edge/signals
mean, place a paper trade on a suggested liquid market). Persist dismissal in
localStorage. Reuse Quest onboarding components. E2E test for the flow.

## ITERATION PROTOCOL (per run)

1. Pick first TODO unblocked ticket; say which and why in one line.
2. Implement smallest green slice; reuse existing modules.
3. Run FULL gate; fix until green; never weaken tests.
4. Fresh-context verifier re-runs gate + adversarially reviews diff vs
   guardrails. Verdict required before DONE.
5. Update this file: ticket status + evidence in a LOOP LOG table row +
   AutoLab line. Commit.
6. Stop. If 3 consecutive iterations make nothing newly DONE, write a
   post-mortem here and reorganize instead of a 4th attempt.

## LOOP LOG

| iter | date | ticket | result | proof |
|------|------|--------|--------|-------|
