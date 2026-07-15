# Loop V30 — Frontend polish (QA-found cosmetics + theme debt)

> Runner: Cursor Grok 4.5 (headless executor). Worktree
> E:/polymarket-worktrees/loop30-polish, branch loop30/polish.

## Ownership
YOURS: frontend/src/**, frontend/e2e/** (only to un-filter fixed bugs), 
goals/loop-v30-polish/**. FOREIGN: backend/**, deploy configs,
OrderbookDepthChart.tsx + chart-colors.* ONLY IF the parallel fix session is
still open — check git log for its commit first; if its fix landed, those
files are fair game for P3.

## Tickets (continuous; commit fix(loop30): <ticket>)
- P1 BUG-V28-01: the public feed/activity trader label ignores display_name
  (shows anon hash even when a display name exists). Respect display_name
  with the anon fallback (same rule as profiles/leaderboard). Un-fixme the
  QA assertion in frontend/e2e.
- P2 BUG-V28-02: TradingView attribution #tv-attr-logo creates a nested-
  interactive inside role="img" (axe serious). Fix properly if the chart
  wrapper allows (aria-hidden on the attribution or restructure roles —
  do NOT hide required attribution visually); then remove the narrow axe
  filter in e2e/a11y.spec.ts. If genuinely unfixable without violating
  TradingView attribution terms, document why and keep the filter with a
  dated justification.
- P3 Light-mode chart theming (old E05 debt): lightweight-charts colors are
  hardcoded dark (grid/text), so charts don't re-theme when .light is set.
  Use the chart-colors.ts runtime-resolution helper pattern to read theme
  tokens and re-apply on theme toggle. Verify both themes by DOM/screenshot
  on the local stack.
- P4 Full gates: typecheck/lint/vitest/build + FULL e2e suite green with the
  un-filtered assertions. Fresh verifier. STOP.
