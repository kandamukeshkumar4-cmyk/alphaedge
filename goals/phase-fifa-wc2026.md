---
id: phase-fifa-wc2026
phase: FIFA
status: ACTIVE
runs_parallel_with: phase-3-forecast-engine
depends_on: [phase-0]
workflow: backend-feature + clv-model-gate
full_spec: docs/handoff/CODEX-fifa-track.md
---

# FIFA World Cup 2026 — parallel sport track (adds to NBA, shares the engine)

> **Codex: read [`docs/handoff/CODEX-fifa-track.md`](../docs/handoff/CODEX-fifa-track.md) first.**
> This is a **parallel track** to [Phase 3 — Forecast Engine v0](phase-3-forecast-engine.md),
> **not** a replacement. NBA work continues and merges; FIFA is additive and must not
> regress NBA. The sport-agnostic forecast harness from Phase 3 is **shared** — we
> add a FIFA market catalog, FIFA features, and the Monte Carlo model.

**Objective:** extend the Kalshi/Polymarket-style **paper-trading** app to cover the
**FIFA World Cup 2026** alongside NBA. An ML pipeline predicts match Win/Draw/Loss
and, via Monte Carlo over the bracket, each team's tournament-win probability. Those
calibrated probabilities surface as the edge signal on each FIFA market, gated on
beating the market's closing line — using the same gate as NBA.

> This is a fun ML exercise, not betting advice. Simulated funds only.

## Reuse, do not rewrite (shared with the NBA track)
- Market shell + order path: `app/market`, `services/market_service.py`,
  RiskService → `OrderIntent` → `OrderBookService`. Paper-trading UI in `frontend/`.
- Forecast harness: `ml/trainer.py` (walk-forward CV, calibration-by-ECE),
  `ml/calibration.py` (Platt+isotonic+reliability), `forecasting/predictor.py`
  (executable-ask CLV + `is_edge` gate), `risk/rules.py` (fractional Kelly, caps),
  `backtesting/significance.py` (paired-bootstrap CLV gate), snapshot capture +
  admin proof UI.

## Build order (one reviewable branch each)

**1. FIFA market catalog + canonical test market.**
**Add** WC2026 markets to `seed_catalog_markets` (do not remove the NBA/election
specs) and add a FIFA canonical test market slug (e.g. a WC2026 group fixture)
**without** changing the NBA canonical `nba-2025-01-15-lal-bos`.

**Market shape (DECIDED — reuse the binary YES/NO order book; no schema change):**
represent every multi-outcome event as a *group of mutually-exclusive binary
markets* (the Kalshi/Polymarket pattern), linked via a shared group slug + the
existing `market_count` field:
  - **Group-stage match** → 3 binary markets `{Home win, Draw, Away win}`. Draws are
    real (no extra time in groups). Each market's YES prob = the model's regulation
    W/D/L probability; the group sums to ~1 before vig (feeds the existing
    de-vig/dutching helpers).
  - **Knockout match** → 2 binary markets `{Team A advances, Team B advances}`. No
    draw market (ET/penalties always produce a winner). Prob comes from the Monte
    Carlo simulator's **advancement** probability, not raw regulation W/D/L.
  - **Tournament winner** → 1 binary market per contender, YES prob = MC P(win cup).
Do **not** add a native 3-way market type (would touch order book/settlement and
risk regressing NBA).

**2. Dataset loaders.** Read the **filename contract + sourcing catalog** in
[`backend/app/data/fifa/README.md`](../backend/app/data/fifa/README.md) — load the
canonical filenames defined there (Tier 0 required: `intl_results.csv`,
`wc2026_fixtures.csv`, `wc2026_bracket.csv`; Tier 1 recommended: `fifa_rankings.csv`,
`intl_elo_ratings.csv`, `intl_shootouts.csv`, `intl_goalscorers.csv`).
Load deterministically; degrade gracefully when an optional file is absent. Use only
provided data — no hardcoded team strength. **The CSVs are gitignored — copy them
into this worktree's `backend/app/data/fifa/` before loading** (the human drops them
in the main repo at `E:\polymarket clone\backend\app\data\fifa\`). The CLV gate's
closing line for FIFA is the **Kalshi/Polymarket market close** (reuse the existing
snapshot capture), NOT a bookmaker odds CSV.

**Confirmed Tier 0 schema (2026-06-06, files are present):**
- `intl_results.csv` (49,411 rows, martj42): `date, home_team, away_team, home_score,
  away_score, tournament, city, country, neutral`. Filter `tournament` for World Cup
  vs friendlies/qualifiers when weighting; `neutral` + `country` drive home-continent.
- `wc2026_fixtures.csv` (72 group rows) and `wc2026_bracket.csv` (32 knockout rows)
  share the areezvisram12 schema: `source_dataset, source_file, id, match_number,
  stage_id, stage_name, stage_order, match_label, home_team_id, home_team_name,
  home_team_code, home_group_letter, home_is_placeholder, away_team_id,
  away_team_name, away_team_code, away_group_letter, away_is_placeholder, city_id,
  city_name, country, venue_name, region_cluster, airport_code, kickoff_at`.
- **Knockout rows have EMPTY team columns**; the bracket is encoded in `match_label`
  tokens: `1X`/`2X` = winner/runner-up of group X (A–L), `3X`/best-third for the
  best-third qualifiers, `WNN` = winner of match number NN. The MC simulator resolves
  these from simulated group/knockout results.
- **Some group fixtures are placeholders** (`home_is_placeholder=True`, names like
  "Winner UEFA Playoff D") — the 6 playoff spots. Treat as TBD until resolved.
- **Known upstream typo:** bracket match 100 `match_label = "W95 vs W100"` is a
  self-reference. The loader must **log/flag** unresolvable bracket tokens (incl. this
  one), NOT silently guess a fix.
- **Team-name reconciliation is required:** join 2026 `home_team_name` to historical
  `home_team`/`away_team` via a canonical key; assert mapping coverage and log any
  unmatched team rather than dropping it silently.

**3. FIFA features** (`ml/features.py`, sport-tagged path — must not break NBA
features): win rate, goal difference, GF/GA per game
(overall + last 3 tournaments), head-to-head, historical stage reached, home-
continent advantage, weighted recency. Keep `assert_no_post_game_leakage`; closing
price is label-only. Sparse-H2H → fall back to overall team strength.

**4. Models** (`ml/`): W/D/L ensemble (LogReg + RandomForest + XGBoost) with CV;
Poisson goals → scoreline simulation; **Monte Carlo tournament simulator (10k runs)**
→ P(win cup) / P(reach final) / P(reach semis) per team, with group tiebreakers
(GD, GF, H2H). Emit feature importances.

**5. Wire-in**: `forecasting/predictor.py` maps each market to its model prob —
group-stage = calibrated regulation W/D/L; knockout = MC advancement prob; winner =
MC P(win cup) — then the existing CLV / significance / Kelly gate decides `is_edge`.
No new gate logic; no NBA regression.

## Acceptance gate
- Out-of-sample walk-forward **CLV positive** AND **Brier < closing-line Brier** for
  the markets where the model claims an edge; otherwise `is_edge=false` (hidden).
- Edge credited only when statistically significant (`assess_closing_edge`).
- A synthetic model that does NOT beat the closing line resolves `is_edge=false`
  (asserted in tests). No-leakage test passes; calibration improves reliability;
  Kelly caps respected; feature importances reported.

## Safety (non-negotiable)
`PAPER_TRADING_ONLY=true`. No execution, no payment rails, no cash-funding language.
LLM/agent code never sets stake, side, or `is_edge`. Never tune thresholds/fixtures
to force `gate=met` (AutoLab/Goodhart guard).

## PR line
`FIFA WC2026 | <component> | gate=<met/blocked> | CLV=<+x.xx> Brier=<model vs closing> | verify=pytest <n> passed, ruff clean | safety=paper-only,no-exec: ok | review=<skill/manual> | AutoLab=baseline=<closing-line Brier> | benchmark=walk-forward CLV | iterations=<n+best> | budget=<used/limit> | outcome=<improved/stalled/retired>`
