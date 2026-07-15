# Loop V44 — Visual regression baselines
> Runner: Cursor Grok 4.5 headless. Worktree E:/polymarket-worktrees/loop44-visreg,
> branch loop44/visreg.
## Mission: the QA suite asserts behavior; nothing guards LOOKS. Add
playwright toHaveScreenshot baselines so visual breakage (theme, spacing,
overflow) fails CI.
## Tickets (test(loop44): <ticket>)
- S1 Stable-shot harness: helpers to mask/freeze dynamic regions (prices,
  sparklines, tickers, ages) so shots are deterministic; document masking
  rules. NO app-code changes to achieve stability — masking only.
- S2 Baselines: /, market detail, /portfolio (empty state), /leaderboard,
  /eval, /admin/observability — both themes, desktop + 375px. Commit
  baseline PNGs; suite green twice consecutively (prove stability).
- S3 CI-safety: baselines platform-tagged so ubuntu CI doesn't fight
  Windows-local renders (playwright snapshotPathTemplate per-platform;
  generate ubuntu baselines via the ci-e2e workflow ONLY if trivially
  possible — otherwise scope the visreg project to local runs and document,
  do NOT break the green CI). Full frontend gates + FULL playwright green
  + verifier. STOP.
## Ownership: frontend/e2e/** + playwright config additive + baseline
assets + goals/loop-v44-visreg/**. Never frontend/src, never break existing
suite/CI, never push/merge.
