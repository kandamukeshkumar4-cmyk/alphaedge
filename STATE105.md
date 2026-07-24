# Loop 105 — honest source labelling

Worktree: `E:\polymarket-worktrees\loop105-honest`
Branch: `loop105-honest/node`

## Scope

Paper-trading simulation only. Fallback data remains available for offline/CI;
this node labels its origin in the same visual region as the affected values.
No backend, order path, secret, deployment, or forbidden file changes.

## Progress

- Item 1 LiveTicker: changed user-facing framing from live to simulated demo feed; proof pending final gate run.
- Item 2 market detail: added fallback banners, propagated demo context to forecast/activity panels, and disabled sample-book jitter unless the existing market source is a live venue.
- Items 3–8: pending.

## Verification

Item 1 focused typecheck:

```text
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
```

## Before → after indicators

1. LiveTicker: `Live trades` + pulsing `live` → `Demo feed` + `simulated` + explicit simulated-trades banner.
2. Market detail: distant paper footer only → visible demo-market banner plus demo forecast/activity/sample-book indicators; sample order-book sizes stop jittering off live-source data.

## Blockers and unrelated findings

- Initial typecheck could not start because `frontend/node_modules` was absent; restored from the existing lockfile with `npm ci`.
- `npm ci` reported 5 high-severity audit findings; no dependency files were changed, and this node does not remediate unrelated dependency issues.

## Commits

- `a719f4a fix(loop105): honest source labelling — demo ticker`
- Item 2 commit will be listed after commit.
