# STATE117 — honestfix ship blockers (items 1–3)

Worktree: `E:/polymarket-worktrees/loop117-honestfix`  
Branch: `loop117-honestfix/node`  
Date: 2026-07-27  
Seat: Cursor Grok 4.5 High (FRONTEND)

## Scope (charter)

Items 1, 2, 3 from `SHIP-REVIEW.md` only:

1. `/alpha` parse real envelope; delete mock fallbacks; badge worst-of all sources
2. Unit + e2e tests assert prod shape / honest truth (prerequisite)
3. PriceChart candle provenance via `fetchMarketCandlesMeta`

Sparkline label (ranked list item 7): **deferred** — not trivial without also editing
`QuestMarketCard.tsx` (out of charter). `useLiveSparkline.ts` left untouched.

## Commits

| Item | SHA | Message |
| --- | --- | --- |
| 1 | `1775f8a` | `fix(loop117): parse real alpha envelope; drop seed mock fallbacks` |
| 2 | `3489af5` | `fix(loop117): alpha tests assert prod envelope and honest empty` |
| 3 | `d495ee8` | `fix(loop117): label PriceChart when candle source is not live` |

## Prod shape confirmation (2026-07-27)

- `GET /api/v1/alpha/runs?limit=3` → keys `["latest","runs","paper_trading_only"]`
- `GET /api/v1/alpha/latest-signal` → `{run_date, signal, rejection_reasons, paper_trading_only}`
- `GET /api/v1/alpha/hypotheses` → `{run_date, hypotheses, rejection_reasons, paper_trading_only}`
- `GET /api/v1/markets/nba-2025-01-15-lal-bos/candles?points=90` → `source: "db"`, 90 candles

## Changes

- `alpha-runs-api.ts` — normalizers read `runs` / `signal` / `hypotheses.*`; mock seeds deleted; fail → honest empty + `source:"mock"`
- `AlphaResearchPage.tsx` — badge = worst-of(factors, report, runs, signal, hypotheses)
- `alpha-runs-api.test.ts` — prod-shape fixtures; asserts invented `items`/`emitted` rejected
- `e2e/alpha-runs.spec.ts` — honest empty OR real rows (no five-seed / four-hypothesis counts)
- `PriceChart.tsx` — consumes `fetchMarketCandlesMeta`; labels seed + db-padded (+ staleness)
- `alphaedge-api.ts` — JSDoc pointing consumers at the meta helper

## AutoLab

AutoLab: not applicable (no iterative measure — honesty/provenance fix)

## VERIFY (verbatim)

### `npx vitest run src/lib/alpha-runs-api.test.ts`

```text
 RUN  v4.1.8 E:/polymarket-worktrees/loop117-honestfix/frontend

 ✓ src/lib/alpha-runs-api.test.ts > alpha-runs-api client > normalizes a live runs payload (prod {latest,runs} envelope) 56ms
 ✓ src/lib/alpha-runs-api.test.ts > alpha-runs-api client > normalizes live latest-signal and hypotheses payloads (prod shapes) 2ms
 ✓ src/lib/alpha-runs-api.test.ts > alpha-runs-api client > returns honest empty (not seed rows) when the live API is down 1ms
 ✓ src/lib/alpha-runs-api.test.ts > alpha-runs-api client > rejects invented items/emitted envelopes (never treats them as live) 1ms

 Test Files  1 passed (1)
      Tests  4 passed (4)
   Start at  13:47:17
   Duration  9.49s (transform 120ms, setup 0ms, import 267ms, tests 61ms, environment 0ms)
```

### `npm run typecheck`

```text
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
```

(exit 0)

### `npm run lint`

```text
> alphaedge-frontend@0.1.0 lint
> eslint .
```

(exit 0)

### `npm run build`

```text
> alphaedge-frontend@0.1.0 build
> next build
```

(exit 0 — Next.js production build completed successfully)

### `npx playwright test e2e/alpha-runs.spec.ts --reporter=list`

```text
Running 2 tests using 1 worker

  ok 1 [chromium] › e2e\alpha-runs.spec.ts:18:7 › Loop102 alpha runs UI › /alpha renders the latest-signal hero and run history (26.8s)
  ok 2 [chromium] › e2e\alpha-runs.spec.ts:76:7 › Loop102 alpha runs UI › /alpha renders hypotheses section (honest empty or real verdicts) (7.7s)

  2 passed (2.0m)
```

(exit 0)

## Deferred / out of charter

- Item 7 sparkline provenance label (`useLiveSparkline` + `QuestMarketCard`) — needs card UI change outside charter
- Items 4–6, 8–14 from ranked fix list — not this pass
- No push / deploy
