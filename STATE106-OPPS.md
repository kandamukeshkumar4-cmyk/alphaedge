# STATE106-OPPS — opportunities empty made EXPLAINABLE (funnel + empty_reason)

Work order: `DIAGNOSIS106-OPPS.md` → "Exact implementation plan for a JUNIOR engineer".
Worktree: `E:/polymarket-worktrees/loop106-opps` · branch `loop106-opps/node` · 2026-07-24.
Seat: implementation engineer (executor). CLV law respected: no fabricated rows,
no weakened thresholds, empty stays a valid outcome — now a named one.

## What was executed (phases in order)

- **Phase 0 — freeze scope.** Edited only the 4 charter files:
  `backend/app/api/v1/opportunities.py`, `backend/tests/test_opportunities_api.py`,
  `frontend/src/lib/opportunities-api.ts`, `frontend/src/app/opportunities/page.tsx`.
  Baseline `pytest -q tests/test_opportunities_api.py`: **8 passed** before edits.
- **Phase 1 — backend.** Added the `funnel` dict (exact field names) set as the
  loop runs, `_opportunities_empty_reason(...)` helper (exact name/docstring,
  exact first-match-wins reason strings), and response fields `"funnel"` +
  `"empty_reason"` (always present, even when non-empty). Ranking math,
  exclusion set, `signal_only`, disclaimer, cache keys untouched. Zero migrations.
- **Phase 2 — tests.** Five new tests with the exact plan names
  (`test_honest_empty_includes_empty_reason_no_model`,
  `test_funnel_counts_with_seeded_edges`,
  `test_empty_reason_filtered_by_min_liquidity`,
  `test_empty_reason_filtered_by_direction`,
  `test_empty_reason_no_open_candidates`); all 8 pre-existing tests untouched
  and green (ranking slug order unchanged).
- **Phase 3 — frontend.** `OpportunitiesResponse` gained optional `funnel` +
  `empty_reason` (exact union); `OpportunitiesView` gained `emptyReason` +
  `funnel`; `buildOpportunitiesView` passes through `raw?.empty_reason ?? null`
  and `raw?.funnel ?? null`. Empty-state body branches on `raw?.empty_reason`
  with the exact plan copy strings; unreachable + client-filter fallbacks kept;
  layout classes unchanged; title unchanged.
- **Phase 4 — NOT implemented (per plan):** no PredictionLog producer, no
  ForecastLog-as-model_p, no alpha/validator/signal_only changes, no migrations,
  no order-path imports. Confirmed: none touched.
- **Phase 5 — verification.** All six stop-condition commands run in the
  foreground; literal last output lines pasted below.

## Notes for the auditor

- **Loop order follows the plan's step-3 enumeration** (model_p → resolve
  market_p → liquidity floor → direction). This order is REQUIRED by
  `test_empty_reason_filtered_by_min_liquidity` (with_model_p==1 and
  empty_reason=="filtered_by_min_liquidity" only hold if market_p resolves
  before the floor). The exclusion SET and ranking math are identical to
  before (independent AND conditions) — all 8 pre-existing tests prove it.
- **Optional items SKIPPED per session rules ("where the plan says optionally,
  SKIP the option"):**
  1. Phase 1 step 2 (`candidates_scanned` population from pre-filter `markets`
     length) — skipped; the field is present in the response and stays `0`.
  2. Optional `alpha_model_edge_valid` response context — skipped; left the
     plan-prescribed `UNVERIFIED / deferred` code comment in opportunities.py.
  3. Optional "Pipeline: open … with model … with price … returned …" small
     print under the empty-state body — skipped; `funnel` + `emptyReason` are
     still exposed on the view model for a future surface.
  4. Optional new frontend unit tests next to `opportunities-api.test.ts` —
     skipped; the pre-existing vitest suite was not modified (its per-field
     assertions stay compatible with the added view fields; `npm run typecheck`
     covers the test file's types).
- **No NEEDS COORDINATION and no NEEDS MIGRATION items arose.**
- Prod read-only GET (`/api/v1/opportunities` → `empty_reason` +
  `funnel.candidates_open > 0`, `funnel.with_model_p == 0`) is a POST-DEPLOY
  check; this node does not deploy and prod still runs the pre-change schema.
- `PAPER_TRADING_ONLY` untouched; no secrets printed/set; no push, no deploy,
  no prod mutation; read-only ASGI-transport tests only.

## STOP CONDITION — verbatim tool output (literal last lines)

```
$ cd backend && uv run --extra dev pytest -q tests/test_opportunities_api.py --basetemp=E:/polymarket-worktrees/loop106-opps/.pt
.............                                                            [100%]
13 passed in 10.49s
```

```
$ cd backend && uv run --extra dev ruff check app tests
All checks passed!
```

```
$ cd backend && uv run --extra dev pytest -q tests/test_openapi_snapshot.py --basetemp=E:/polymarket-worktrees/loop106-opps/.pt2
...                                                                      [100%]
3 passed in 6.60s
```

(no regen needed — the endpoint returns a plain `Response` with no
`response_model`, so the added body fields do not change the OpenAPI schema)

```
$ cd frontend && npm run typecheck
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
```

(exit 0; tsc prints no diagnostics on success)

```
$ cd frontend && npm run lint
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
```

(exit 0; eslint --max-warnings=0 prints nothing on a clean run)

```
$ cd frontend && npm run build
…
○  (Static)   prerendered as static content
●  (SSG)      prerendered as static HTML (uses generateStaticParams)
ƒ  (Dynamic)  server-rendered on demand
```

(exit 0; Next.js production build completed)

AutoLab: not applicable (no iterative measure — one-shot explainability fix;
success metric per plan is "ops can answer 'empty because no model
predictions' without DB SSH", verified by the funnel/empty_reason tests above).

Execution Gate claimed: backend pytest + ruff and frontend lint/typecheck/build
green per AGENTS.md §3 per-surface verification; no later gate claimed.

done

## git log --oneline

```
bd2463c feat(loop106): opportunities empty-state copy keyed on empty_reason
62a1b0b feat(loop106): funnel + empty_reason coverage for opportunities API
bc87631 feat(loop106): opportunities funnel counts + machine-stable empty_reason
67b380b docs(loop105): final prod smoke HEALTHY — wave 105 verified end to end
328afd8 merge(loop105): pagination-aware frontend — Load more + explicit limits (Cursor; Grok audit PASS, no blockers)
c497306 feat(loop105): record catalog UI gate proofs in STATE105-CATALOGUI
6182b15 docs(loop106): record gate output and handoff state in STATE106.md
c869d44 fix(loop106): point calibration bins at the real eval endpoint
a2aa006 merge(loop105): alpha validation provenance — the model can finally learn (Sol; Grok audit PASS, no blockers)
c771a48 docs(loop105): record provenance proof
61ac7bf merge(loop105): /markets pagination — 2.35MB -> 45KB default (Cursor; audit PASS WITH FIXES, both fixed)
892d3ef fix(loop105): stable sort tiebreak + explicit internal caller limits
```
