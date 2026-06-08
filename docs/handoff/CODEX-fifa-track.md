# Codex Briefing — FIFA World Cup 2026 as a PARALLEL track (NBA continues)

> Created: 2026-06-06. **This does NOT stop the NBA Phase-3 work.** It adds a
> second sport track that shares the same forecast engine. Keep the Phase-3
> branches/worktrees going to completion + merge; add FIFA alongside.

---

## TL;DR

We are **adding FIFA**, not replacing NBA. The app becomes a multi-sport
Kalshi/Polymarket-style **paper-trading** app covering **both NBA and FIFA World
Cup 2026** markets. The forecast harness Codex already built is sport-agnostic and
is **shared** by both tracks. FIFA is a new feature builder + a new Monte Carlo
model feeding that same harness.

## Why parallel works cleanly (do not throw away NBA work)

1. None of the Phase-3 branches are merged yet — nothing is lost. Finish + merge
   them on their own schedule.
2. The harness is already sport-agnostic: `ml/trainer.py` (walk-forward CV,
   calibration-by-ECE), `ml/calibration.py` (Platt+isotonic+ECE),
   `forecasting/predictor.py` (executable-ask CLV + `is_edge` gate),
   `risk/rules.py` (fractional Kelly), `backtesting/significance.py`
   (paired-bootstrap CLV gate), snapshot capture + admin proof UI.
3. The market catalog already holds multiple markets/sports
   (`services/market_service.py::seed_catalog_markets` seeds NBA + an election
   market today). FIFA markets are **added** to that catalog, NBA stays.

## Two tracks, run as separate worktrees (same pattern as phase3-1..4)

- **NBA track (existing):** the `phase3-*` branches + the historical closing-line
  snapshot-capture/admin-proof thread. Continue as-is. Canonical market stays
  `nba-2025-01-15-lal-bos`.
- **FIFA track (new):** `goals/phase-fifa-wc2026.md`. New branch(es). Shares the
  harness; adds FIFA markets, FIFA features, and the Monte Carlo tournament model.

## ⚠️ Data location across worktrees (do this first, before loaders)

The raw FIFA CSVs are **gitignored**, so they do **not** travel to your worktree
through git. The human drops the Tier 0 files in the **main repo**:

```
E:\polymarket clone\backend\app\data\fifa\
  intl_results.csv
  wc2026_fixtures.csv
  wc2026_bracket.csv
```

**Before running any loader, copy those files into your own worktree's
`backend/app/data/fifa/` directory.** Do not assume they are already present in the
worktree just because the path exists.

## FIFA track build order (one reviewable branch each)

1. **FIFA market catalog**: add WC2026 markets to `seed_catalog_markets` —
   per-match outcome markets + one binary tournament-winner market per contender
   (Polymarket-style). Add a FIFA canonical test market (do not remove the NBA one).
2. **Dataset loaders**: read `backend/app/data/fifa/README.md` for the filename
   contract; load the Tier 0/Tier 1 canonical files under `backend/app/data/fifa/`
   (after copying them into your worktree — see the data-location note above).
   Load deterministically; degrade gracefully when an optional file is absent.
   Use only provided data — no hardcoded team strength. Sparse H2H → fall back to
   overall team strength. **The two WC2026 datasets are community/unofficial — their
   column layout varies. Read the actual headers and adapt the loader; do NOT assume
   a fixed schema. Log the columns you found** so the human can sanity-check the
   group/bracket parsing. The CLV gate's closing line for FIFA is the
   Kalshi/Polymarket market close (reuse the snapshot capture), NOT a bookmaker CSV.
3. **FIFA features**: a sport-tagged feature path (do not break NBA features) —
   win rate, goal difference, GF/GA per game (overall + last 3 tournaments),
   head-to-head, historical stage reached, home-continent advantage, weighted
   recency. Keep `assert_no_post_game_leakage`; closing price is label-only.
4. **Models**: W/D/L ensemble (LogReg + RandomForest + XGBoost) with CV; Poisson
   goals → scoreline simulation; **Monte Carlo tournament simulator (10k runs)** →
   P(win cup)/P(reach final)/P(reach semis) per team with group tiebreakers
   (GD, GF, H2H). Emit feature importances.
5. **Wire-in**: `forecasting/predictor.py` consumes calibrated match prob (and MC
   tournament prob for winner markets) as the model prob; existing CLV /
   significance / Kelly gate decides `is_edge`. No new gate logic; no NBA regression.

## Guardrails (unchanged, non-negotiable, both tracks)

- `PAPER_TRADING_ONLY=true`. Simulated funds only. No execution, no payment rails,
  no cash-funding language. Fun ML exercise, not betting advice.
- LLM/agent code never sets stake, side, or `is_edge`. Only path:
  RiskService → `OrderIntent` → `OrderBookService`.
- **AutoLab / Goodhart guard**: never tune thresholds/min-sample/fixtures to force
  `gate=met`. A model that doesn't beat the closing line resolving `is_edge=false`
  is the correct outcome.
- FIFA changes must not regress NBA tests. Keep the repo green for both sports.

## Required PR line

```text
FIFA WC2026 (parallel) | <component> | gate=<met/blocked> | CLV=<+x.xx> Brier=<model vs closing> | verify=pytest <n> passed, ruff clean | safety=paper-only,no-exec: ok | nba-regression=none | AutoLab=baseline=<closing-line Brier> | benchmark=walk-forward CLV | iterations=<n+best> | budget=<used/limit> | outcome=<improved/stalled/retired>
```
