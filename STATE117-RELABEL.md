# STATE117-RELABEL — D0 copy-honesty fix: labels say market-baseline until an artifact activates

**Role:** Implementer (bounded copy fix)
**Worktree:** `E:/polymarket-worktrees/loop117-relabel`
**Date:** 2026-07-27
**Work order:** loop117 D0 — relabel per `SCHED-DIAG117.md` § "Label map for copy-fix"
**Scope discipline:** strings at mapped locations only + the one `/eval` explainer line.
No number, computation, or layout changes. No secrets, push, or deploy.

**AutoLab:** not applicable (no iterative measure)

---

## Verification (verbatim)

Environment setup (no code change): worktree `frontend/` had no `node_modules`;
ran `npm ci --no-audit --no-fund` → `added 649 packages in 49s` (node v24.14.0, npm 11.9.0).

```text
$ cd frontend && npm run typecheck

> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit

(exit 0)

$ npm run lint

> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0

(exit 0)

$ npx vitest run

 RUN  v4.1.8 E:/polymarket-worktrees/loop117-relabel/frontend

 Test Files  101 passed (101)
      Tests  569 passed (569)
   Start at  14:09:51
   Duration  12.11s (transform 4.82s, setup 0ms, import 18.10s, tests 4.02s, environment 20ms)
```

All three gates green on first attempt. 0 failures.

---

## Relabel ledger (old → new)

### Primary ship surfaces (work-order example mappings, applied verbatim)

| file | old | new |
|---|---|---|
| `frontend/src/app/eval/page.tsx:92` | kicker `Model proof` | `Forecast track record` |
| `frontend/src/app/eval/page.tsx:100` | `Mean Brier (7d)` | `Mean Brier (7d) — market-baseline` |
| `frontend/src/app/eval/page.tsx:115` | `Ensemble vs single-model (U08 AutoLab)` | `Ensemble vs single-model (U08 AutoLab) — market-baseline` |
| `frontend/src/app/eval/page.tsx:160` | `Single-model Brier` | `Single-model Brier (market-baseline)` |
| `frontend/src/app/resolved/page.tsx:70` | `model {row.modelLabel}` | `forecast {row.modelLabel}` |
| `frontend/src/app/resolved/page.tsx:132` | `the model's probability at close` | `the recorded probability at close (market-implied baseline)` |
| `frontend/src/app/resolved/page.tsx:149` | `Model accuracy` | `Baseline accuracy (market-implied)` |
| `frontend/src/app/resolved/page.tsx:160` | `Mean Brier` | `Mean Brier (market-implied)` |

### Explainer (one new DOM line, real rendered text)

`frontend/src/app/eval/page.tsx` — `<p className="mt-3 text-xs leading-relaxed text-muted-2">`
inserted directly below the headline aggregates block (always rendered, both API-up and
API-down states):

> Current predictions mirror market prices (baseline). Model-generated forecasts appear here once a trained artifact is activated.

### Secondary surfaces (label-map table 2)

| file:line | old | new |
|---|---|---|
| `compare/page.tsx:76` | `Model vs market` | `Forecast vs market` |
| `compare/page.tsx:80` | `model {col.modelLabel}` | `forecast {col.modelLabel}` |
| `s/[slug]/share-client.tsx:100` | `Model vs market` | `Forecast vs market` |
| `s/[slug]/share-client.tsx:103` | `model {view.modelLabel}` | `forecast {view.modelLabel}` |
| `categories/[category]/category-client.tsx:68` | `how far the model sits from the market` / `how the model has actually done` | `how far the recorded forecast sits from the market` / `how the recorded forecast has actually done` |
| `alerts/page.tsx:99` | `Model mispricings` | `Forecast mispricings` |
| `alerts/page.tsx:147` | `model mispricings` | `forecast mispricings` |
| `opportunities/page.tsx:97` | `stored model probability` / `model-vs-market scanner` | `stored forecast probability` / `forecast-vs-market scanner` |
| `opportunities/layout.tsx:7` | `Model-vs-market opportunity board` | `Forecast-vs-market opportunity board` |
| `signals/layout.tsx:7` | `Model-vs-market signal desk` | `Forecast-vs-market signal desk` |
| `screener/layout.tsx:12` | `ranked by model edge` | `ranked by forecast edge (market-baseline)` |
| `screener/page.tsx:5` (comment) | `ranked by model edge` | `ranked by forecast edge (market-baseline)` |
| `home/page.tsx:170` | `Model A/B readiness` | `Forecast A/B readiness` |
| `home/page.tsx:284` | `Model A/B readiness` | `Forecast A/B readiness` |
| `BacktestWalkForward.tsx:131` | `Model Brier` | `Model Brier — market-baseline` |
| `SelfServeBacktest.tsx:135` | `Model Brier` | `Model Brier — market-baseline` |
| `BriefEvidencePanel.tsx:30` | `Model vs market` | `Forecast vs market` |
| `DeskIntelligencePanel.tsx:112` | `Model vs market` | `Forecast vs market` |
| `DeskIntelligencePanel.tsx:116` | `model {view.edge.modelLabel}` | `forecast {view.edge.modelLabel}` |
| `ForecastDriversPanel.tsx:48,57,70` | `Why the model thinks this` | `Why the forecast reads this way` |
| `ForecastDriversPanel.tsx:78` | `model {…} vs market {…}` | `forecast {…} vs market {…}` |
| `EdgeHistoryChart.tsx:50,52` | `Model vs market edge history over …` (aria + `<title>`) | `Forecast vs market edge history over …` |
| `EdgeHistoryChart.tsx:109,118,135` | `Model vs market history` | `Forecast vs market history` |
| `EdgeHistoryChart.tsx:159` | `model {view.latest?.modelLabel}` | `forecast {view.latest?.modelLabel}` |
| `SignalEvidence.tsx:14` | `model {…}%` | `forecast {…}%` |
| `DecisionCard.tsx:418` | `Provisional — model not yet CLV-validated` | `Provisional — forecast not yet CLV-validated` |
| `backtest-summary-api.ts:121` | verdict `model beats market` | `baseline beats market` |

### Judgment calls (documented, not guessed)

1. **Same-string siblings in mapped files** — `ForecastDriversPanel.tsx:68`
   (`aria-label="Why the model thinks this"`) and `EdgeHistoryChart.tsx:133`
   (`aria-label="Model vs market edge history"`) carry the exact mapped strings two lines
   from their mapped siblings (the map listed the paired aria-labels at 50/52 but not these).
   Relabeled to keep each section's aria-label matching its visible title. "Find the string
   nearby" per work order.
2. **Verdict family** — the mapped verdict at `backtest-summary-api.ts:121` is one ternary
   with three literals. All three relabeled together (`baseline beats market` /
   `market beats baseline` / `baseline ties market`) plus the JSDoc at line 53, so the value
   space stays internally consistent and documented. "Baseline" (not "forecast") here to pair
   with the adjacent tile label `Model Brier — market-baseline` and the existing
   `Market Brier` tile hint "implied-price baseline".
3. **Test expectations tied to mapped strings** (required for green vitest; string-only):
   - `backtest-summary-api.test.ts:66`: `toBe("model beats market")` → `toBe("baseline beats market")`
   - `feature-surfaces.test.tsx:143`: `toContain("Model vs market")` → `toContain("Forecast vs market")`
4. **Numbers untouched** — Brier 0.0811…, accuracy 0.8711, n=225, all `.toFixed()` formats,
   all computations and layout unchanged. `git diff` is strings-only plus the one new `<p>`.

### Unmapped twins / residue (left untouched per "mapped locations only" — candidates for a follow-up)

- `lib/backtest-run-api.ts:168` — identical verdict family (`model beats market` etc.)
  feeding `SelfServeBacktest`'s hint; not in the label map. The self-serve tile label now
  says `Model Brier — market-baseline` while its hint can still read "model beats market".
- `app/markets/[slug]/market-detail-client.tsx:46` — `PROVISIONAL_LABEL` twin of
  DecisionCard:418 (`⚠️ Provisional — model not yet CLV-validated`).
- `lib/site-metadata.ts:79/151/247` — sitemap-registry copies of the signals/opportunities/
  screener meta descriptions (page `<meta>` comes from the layout files, which were relabeled).
- `components/OpportunityCard.tsx:45` (`model {row.modelLabel}`), `BriefEvidencePanel.tsx:35`
  (`Metric label="Model"`), `EdgeHistoryChart.tsx:43` (`desc`), plus various `lib/*` fixture
  strings and code comments (e.g. `scanners-api.ts:484`, `terminal-api.ts`, `skills-api.ts:119`,
  `marketplace-api.ts:211`, `opportunities-api.ts:124`, `edge-history-api.ts:68`,
  `category-summary-api.ts:59`, `feature-registry.ts:64`).

No mapped string was absent; no line had moved. Nothing was guessed.

## Handoff

D0 copy now frames every mapped surface as market-baseline / recorded forecast while
`provenance_model_types == ["implied_passthrough"]`. When a trained artifact activates,
relabel back (or make the qualifier provenance-conditional) — the residue list above is the
starting inventory for that pass.

---

## useLiveMarket fix

**Date:** 2026-07-27 (second micro-fix on this worktree, on top of the merged relabel commit)
**Scope:** `frontend/src/hooks/useLiveMarket.ts` ONLY.

Bug flagged by the detail-chain node: `ws.onmessage` parsed the frame as
`{ yes?: number; ts?: number }` and guarded on `typeof d.yes !== "number"`, but the
`/api/v1/ws/prices` frame is actually `{slug, yes_price, ts}` — so the guard rejected
every tick and the hook silently dropped all WS updates instead of crashing.

Fix mirrors the corrected `parsePriceFrame` pattern from
`E:/polymarket-worktrees/loop117-detail/frontend/src/hooks/useMarketPrice.ts`
(fixed in loop117-detail): accept `yes_price` (with `yes` as a legacy-publisher
fallback), coerce to number, apply only when finite and within 0–1, otherwise drop
the frame (publish nothing). `ts` is coerced with a `Date.now() / 1000` fallback,
matching the file's existing convention. HTTP-poll path (`fetchLatestPrice`) untouched.

### Verification (verbatim)

```text
$ cd frontend && npm run typecheck ; npx vitest run

> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit

(exit 0)

 RUN  v4.1.8 E:/polymarket-worktrees/loop117-relabel/frontend

 Test Files  101 passed (101)
      Tests  569 passed (569)
   Start at  15:36:18
   Duration  12.22s (transform 4.40s, setup 0ms, import 17.40s, tests 4.06s, environment 27ms)
```

Both gates green on first attempt. 0 failures.

**AutoLab:** not applicable (no iterative measure)
