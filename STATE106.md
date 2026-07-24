# STATE106 — calibration bins pointed at the real eval endpoint

Branch: `loop106-calib/node` · Date: 2026-07-24

## The bug

`fetchCalibrationBins` in `frontend/src/lib/calibration-api.ts` fetched
`/api/v1/calibration`, which 404s in prod. The real endpoint is
`/api/v1/eval/calibration` (backend `app/api/v1/eval_routes.py`, router prefix
`/api/v1/eval` + route `/calibration`), returning
`{"bins":[{"bin":0,"count":0,"mean_pred":0.0,"mean_outcome":0.0}, ...]}` —
exactly the shape the client already parses. Net effect before the fix:
`fetchCalibrationBins` always returned `[]` (the 404 hit the `!res.ok` guard)
and every calibration curve rendered from nothing, silently.

## The change (charter files only)

1. `frontend/src/lib/calibration-api.ts` — exactly two edits:
   - the fetch path: `"/api/v1/calibration"` → `"/api/v1/eval/calibration"`
   - the doc comment above the types: `GET /api/v1/calibration` →
     `GET /api/v1/eval/calibration`
   Nothing else in the file changed (parsing, `hasLiveApi` gating, error
   fallback to `[]` all untouched).
2. `frontend/src/lib/calibration-api.test.ts` — added a `fetchCalibrationBins`
   describe block with two tests (the pre-existing `buildCalibrationCurve`
   tests were kept verbatim):
   - `calibration_bins_fetches_the_eval_calibration_path` — stubs global
     fetch, asserts some requested URL matches `/api/v1/eval/calibration`
     followed by end-or-`?`, asserts NO requested URL matches a bare
     `/api/v1/calibration` followed by end-or-`?`, and asserts the mocked
     `{ bins: [{bin:0, count:2, mean_pred:0.1, mean_outcome:0.2}] }` payload
     is returned verbatim (parsing untouched).
   - `calibration_bins_returns_empty_on_http_error` — stubs fetch to a
     non-ok response, asserts `[]` (existing behaviour preserved).
   Test env note: vitest runs with `environment: "node"`, so
   `ensureApiBase()` probes `localhost:8000/health` through the same stubbed
   fetch (ok probe → local dev base, non-ok probe → HF prod base); either way
   `hasLiveApi(base)` is true and the calibration fetch is issued against the
   stub — no real network, no function weakening.

## Gate output (verbatim, foreground)

### `cd frontend && npx vitest run src/lib/calibration-api.test.ts`

```
RUN  v4.1.8 E:/polymarket-worktrees/loop106-calib/frontend


 Test Files  1 passed (1)
      Tests  6 passed (6)
   Start at  19:52:38
   Duration  1.91s (transform 181ms, setup 0ms, import 233ms, tests 8ms, environment 0ms)
```

(6 tests = 4 pre-existing `buildCalibrationCurve` + 2 new
`fetchCalibrationBins`.)

### `cd frontend && npm run typecheck`

```
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
```

Exit code 0 (tsc prints nothing on success).

### `cd frontend && npm run lint`

```
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
```

Exit code 0 (eslint with `--max-warnings=0` printed nothing).

## Environment note (not a code change)

First test run hit the known `ECOMPROMISED` npm error: this fresh worktree had
no `frontend/node_modules`, so `npx` tried to download vitest and tripped the
lock check. Ran `npm ci` inside `frontend/` (installs exactly from
`package-lock.json`; lock and package.json untouched — `git status` shows
only the two charter files modified). `npm ci` also reported "5 high severity
vulnerabilities" from `npm audit`; deliberately NOT fixed — `npm audit fix`
would rewrite the lockfile, outside charter.

## Guardrails

PAPER_TRADING_ONLY untouched. No number/probability/copy changes. No secrets
printed or set. Nothing pushed, nothing deployed. Charter held: only
`frontend/src/lib/calibration-api.ts`, `frontend/src/lib/calibration-api.test.ts`,
and this file touched.

AutoLab: not applicable (no iterative measure) — one-shot path fix pinned by a
regression test.

## `git log --oneline`

```
c869d44 fix(loop106): point calibration bins at the real eval endpoint
a2aa006 merge(loop105): alpha validation provenance — the model can finally learn (Sol; Grok audit PASS, no blockers)
c771a48 docs(loop105): record provenance proof
61ac7bf merge(loop105): /markets pagination — 2.35MB -> 45KB default (Cursor; audit PASS WITH FIXES, both fixed)
892d3ef fix(loop105): stable sort tiebreak + explicit internal caller limits
3a72bd6 docs(loop105): record catalog pagination proofs in STATE105
4f77e26 merge(loop104): a11y sweep — 25 routes, 0 serious/critical (Qwen; report caught false, code verified + regression fixed by Grok)
09a2006 fix(loop104): stop chart skeleton claiming the loaded chart's a11y name
41d7bf1 merge(loop105): honest source labelling across 8 decision surfaces (Luna; audit PASS WITH FIXES -> fixed)
132b8c1 fix(loop105): persist alpha validation provenance
f769aab test(loop105): align smoke assertions with honest copy
4140052 fix(loop105): wire terminal auth + honest demo forecast chip
```
