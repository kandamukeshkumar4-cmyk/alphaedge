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
- Item 3 terminal research: 401 responses now produce a sign-in empty state; offline mock sessions carry a loud `PAPER MOCK SESSION — not live research` banner.
- Item 4 trade controls: relabeled buy/close controls, progress states, toasts, money fields, and position values as paper-only; order and risk logic untouched.
- Item 5 PriceChart: generated candle fallback now carries an adjacent visible `Synthetic chart` indicator.
- Item 6 marketplace spotlight: now honors the existing trending/featured `source` values and banners mock rows as a paper mock catalog.
- Item 7 Quest board: tracks the bundled seed fallback, adds a visible seed-catalog banner, suppresses seed `LIVE` treatment, and labels team links `Paper buy`.
- Item 8: pending.

## Verification

Item 1 focused typecheck:

```text
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
```

## Before → after indicators

1. LiveTicker: `Live trades` + pulsing `live` → `Demo feed` + `simulated` + explicit simulated-trades banner.
2. Market detail: distant paper footer only → visible demo-market banner plus demo forecast/activity/sample-book indicators; sample order-book sizes stop jittering off live-source data.
3. Terminal research: quiet `· local mock` and fabricated 401 fallback → loud `PAPER MOCK SESSION — not live research`, or a sign-in empty state with no fabricated session.
4. Trade controls: `Buy` / `Placing order…` / `Order placed` → `Paper buy` / `Placing paper order…` / `Paper order placed`; position close and money labels use the same paper framing.
5. PriceChart: unlabeled generated OHLCV fallback → adjacent `Synthetic chart — generated from sample data, not live candles.` text.
6. Marketplace: mock trending/featured cards with silent ratings/run counts → source-driven `Paper mock catalog` banner on each mock row.
7. Quest board: seed cards with quiet `Paper sim` clock plus `Buy LAL/BOS` → visible seed-catalog banner, no seed `LIVE` badge, and `Paper buy LAL/BOS` links.

## Blockers and unrelated findings

- Initial typecheck could not start because `frontend/node_modules` was absent; restored from the existing lockfile with `npm ci`.
- `npm ci` reported 5 high-severity audit findings; no dependency files were changed, and this node does not remediate unrelated dependency issues.

## Commits

- `a719f4a fix(loop105): honest source labelling — demo ticker`
- `6f68956 fix(loop105): honest source labelling — market detail`
- `041fd5f fix(loop105): honest source labelling — terminal research`
- `0444579 fix(loop105): honest source labelling — paper trade controls`
- `8b0194d fix(loop105): honest source labelling — synthetic chart`
- `550c8b5 fix(loop105): honest source labelling — marketplace`
- Item 7 commit will be listed after commit.
