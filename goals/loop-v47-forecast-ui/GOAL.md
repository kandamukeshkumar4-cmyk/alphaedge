# Loop V47 — Forecast transparency UI
> Runner: Cursor Grok 4.5 headless. Worktree E:/polymarket-worktrees/loop47-forecast-ui,
> branch loop47/forecast-ui.
## Mission: the bridge+autolock now lock real forecasts (415 markets in the
funnel) — but users can't SEE them. Surface the locked forecast on market
detail: "Model: locked X% on <date> · market now Y%" honest chip/panel.
## Tickets (feat(loop47): <ticket>)
- F1 Read the backend first: find/confirm the endpoint exposing a market's
  LIVE ForecastLog (forecast_routes / market detail). If none is public,
  STOP and file BLOCKED-ON-BACKEND in STATE.md with the exact shape needed
  (do NOT build backend yourself).
- F2 Detail-page forecast panel: locked probability, lock time (relative),
  vs current market price with delta; honest empty state pre-lock
  ("Model forecast locks near close"); PROVISIONAL disclaimer; both themes.
- F3 Track-record page: show forecast_scored_count + source field honestly
  (from the updated resolved-count endpoint). Full frontend gates (COUNTS)
  + FULL playwright green (+ update visreg baselines if the detail page
  changes: regenerate + 2x green) + fresh verifier. STOP.
## Ownership: frontend/src/**, visreg baseline regeneration if needed,
goals/loop-v47-forecast-ui/**. Design rules apply; never fabricate a
probability; never backend/deploy edits; never push/merge.
