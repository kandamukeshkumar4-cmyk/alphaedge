# STATE116-ARTIFACT — the fired-alert dashboard document

Closes **VIDEO-PARITY-AUDIT.md gap #2** (Video 1 row 30, Video 2 row 38 — the
"rendered alert dashboard artifact", the only MISSING item that appears four
separate times across the two videos).

Branch: `loop116-artifact/node`
Worktree: `E:/polymarket-worktrees/loop116-artifact`
Base: `67d45984dfa814d71dde8423bbbb50a5eaf6b2da` (integration tip,
"feat(loop115): featured curation — flagship four")

---

## What the videos show vs what AlphaEdge had

The videos' payoff moment is a **rendered result document** after a scan fires:
eyebrow, headline, `fired` pill, generated-at + counters, KPI tiles, an action
list, a chart, a per-candidate table, "WHAT THIS MEANS" and "WHAT TO DO NOW".

AlphaEdge rendered a step list and a repair ledger. The pipeline existed; the
artifact did not. It does now, end to end.

---

## What shipped

### Backend

**`backend/app/services/scanner_artifact_service.py`** (new)
Assembles the structured artifact from a finished run:

```
{artifact_version, headline, fired, run_meta{scanner_id, scanner_name, run_id,
 status, started_at, finished_at, duration_ms, interval_minutes, next_run_at,
 is_test, spec_version, paper_trading_only},
 kpis[{label, value, delta?}], step_counters[{index, step, type, in, out,
 measured}], matches[{market_slug, title, category, price, volume, lock_at,
 score, scores{<STEP_TYPE>: {...}}}], chart{type, title, value_label, series,
 empty_reason}, narrative{what_this_means, what_to_do_now[], generator,
 filtered}, generated_at}
```

* Every number is deterministic, computed from the run row plus the mirrored
  `markets` table (one `IN` query for volume/lock time). Nothing is invented:
  price comes from a reading captured during the run (`MODEL_EDGE.market_prob`,
  else `CROSS_VENUE_DIVERGENCE.pm_implied`), never a fresh quote, and is `null`
  when no step recorded one.
* KPI tiles: **Matches** (with a run-over-run `delta` against the previous
  completed/empty run), **Top match**, **Soonest lock**, **Universe scanned**.
* `score` is a labelled composite signal-strength magnitude across whichever
  step reads exist. Steps that did not run contribute nothing — absence is not
  a zero reading.
* Narrative may use the LLM: same route (`llm_route_analyst`), same client
  (`resolve_routed_client`), and the **same `app.agents.analyst._LLM_SEMAPHORE`**
  the analyst briefs use (the NIM free tier 503s on bursts). Unconfigured key,
  timeout, bad JSON or any exception all fall back to the deterministic
  template. `narrative.generator` is always one of `llm` / `llm-filtered` /
  `deterministic`.

**PAPER LAW enforcement.** 22 word-boundary-anchored patterns
(`buy`, `sell`, `bought`, `sold`, `purchase`, `stake`, `wager`, `bet`,
`go long/short`, `long/short position`, `position size`, `entry price`,
`take-profit`, `stop-loss`, `allocate`, `invest`, `take the YES side`,
`YES/NO shares`, `open a trade`, `close the position`, `place an order`, …).
LLM output is filtered **sentence by sentence** for `what_this_means` and
**bullet by bullet** for `what_to_do_now`; a fully-stripped section falls back
to the template. `\b` anchoring means "better" and "sellers" survive — tested.
The deterministic templates are research-only by construction: watch, compare,
read the brief, review the step counters, re-run, widen the filters.

**`backend/app/api/v1/scanner_artifacts.py`** (new)
`GET /api/v1/scanners/{scanner_id}/runs/{run_id}/artifact`. Visibility mirrors
`scanners.py`'s `_get_visible_scanner` exactly — public scanners readable by
anyone, private ones owner-only, misses always **404 (never 403)** so scanner
existence does not leak. Stored artifacts are served verbatim
(`source: "stored"`); runs recorded before the column existed, and failed runs,
are assembled deterministically on read (`source: "on-read"`) with **no LLM call
and no write** — a GET stays a GET.

**Migration `070_scanner_run_artifact`** (chains `069_ident_text`; single head).
Adds the nullable `scanner_runs.artifact` JSON column. `checkpoint` holds resume
state and `result` is an already-consumed API contract, so neither was reusable.
Resilience mirrors 067/068/069: autocommit block, `SET LOCAL lock_timeout=5s`,
bounded retries on `40P01/55P03/57014/40001`, `information_schema` idempotency,
offline-mode refusal. `ADD COLUMN … NULL` takes only a brief lock, no rewrite.
Model field added to `ScannerRun` so `test_migration_exercise` parity holds.

**Executor wiring** (`scanner_executor_service.py`, 4 small edits):
`step_counters` accumulate the real per-step in/out funnel as the run
progresses — a candidate dropped at step 3 is unrecoverable from the final
candidate list, so this had to be measured, not derived. `_attach_artifact` is
called on **both** terminal success paths (the `universe_count == 0` early
return and the normal completion), so fired *and* clean-empty runs get a
document. The import is lazy and every failure is swallowed: a presentation-layer
error can never fail a scan.

### Frontend

**`frontend/src/components/scanners/RunArtifact.tsx`** (new) — eyebrow, headline,
`FIRED` / `NO FIRE` pill, KPI tiles with delta, the step-counter funnel, the
matched-markets table with per-step read chips and market links, the chart, and
both narrative sections as **real DOM text** (selectable, crawlable, screen-
reader readable). Provenance strip states the narrative generator, whether trade
language was filtered, and that the document is research only.

Chart: `lightweight-charts` `HistogramSeries` (the app's chart lib, same
theme-observer/resize teardown pattern as `UsageActivityChart`), lazily imported.
**The time scale is hidden on purpose** — matched markets are categorical and
the library is time-indexed, so market names live in a numbered DOM legend under
the canvas and nothing on the chart claims to be a date.

**`ScannerDetailShell.tsx`** — one import + a 9-line block. The artifact renders
**above** the existing "Latest run" panel. The step list, repair ledger, runs
history and every control are untouched.

**`scanners-api.ts`** — artifact types + `getRunArtifact()`. **Live only, by
design**: there is no mock artifact, because fabricating a fired dashboard is
precisely the fake payoff this surface exists to replace. No artifact → the
component renders nothing.

---

## Honest limitations

* `step_counters.measured` is `false` for intermediate steps of runs recorded
  **before** this loop — the funnel is shown dashed and labelled
  "(not measured)" rather than back-filled with a guess.
* `matches[].price` is a reading captured mid-run, not a live quote, and is
  `null` when no step recorded one.
* Failed / timed-out runs are **not** stamped with an artifact by the executor;
  the endpoint assembles one on read if asked.
* The chart's x-axis carries no meaning (see above) — this is a deliberate
  trade-off to stay on the app's single chart library.
* The e2e spec runs on the in-memory mock, so it can only assert the artifact is
  **absent** there. Live rendering is covered by the backend endpoint tests.

---

## STOP CONDITION — verbatim

**1. Targeted pytest**

```
$ cd backend && uv run --extra dev pytest tests/test_loop116_artifact.py \
    tests/test_loop113_sluglen.py tests/test_loop114_sluglen.py -q -p no:cacheprovider
.............................                                            [100%]
29 passed in 12.20s
```

(25 in `test_loop116_artifact.py` + the two retargeted alembic-head suites.)

**2. Affected-surface pytest** (openapi snapshot, authz matrix, scanner suites)

```
$ cd backend && uv run --extra dev pytest tests/test_openapi_snapshot.py \
    tests/test_loop26_authz_matrix.py tests/test_scanner_executor.py \
    tests/test_scanners_api.py tests/test_scanner_testmode.py \
    tests/test_scanner_fired_alert.py tests/test_alembic_docstrings_v70.py -q
...................                                                      [100%]
19 passed in 39.86s
```

**3. ruff**

```
$ cd backend && uv run --extra dev ruff check app tests
All checks passed!
```

**4. alembic heads**

```
$ cd backend && uv run alembic heads
070_scanner_run_artifact (head)
```

Single head. `070_scanner_run_artifact` → `069_ident_text` → `068_sluglen_text`.

**5. openapi snapshot regen** (routes changed — one route added)

```
$ cd backend && uv run python scripts/regen_openapi_snapshot.py
wrote E:\polymarket-worktrees\loop116-artifact\backend\tests\fixtures\openapi_snapshot.json (210 paths)

$ git diff --stat backend/tests/fixtures/openapi_snapshot.json
 backend/tests/fixtures/openapi_snapshot.json | 9 +++++++++
 1 file changed, 9 insertions(+)
```

Additive only — no path or operation removed or renamed.

**6. Frontend typecheck + lint + build**

```
$ cd frontend && npm run typecheck
> tsc --noEmit
(clean, no output)

$ cd frontend && npm run lint
> eslint src --max-warnings=0
(clean, no output)

$ cd frontend && npm run build
✓ Compiled successfully
+ First Load JS shared by all                     103 kB
(all routes emitted; /scanners and /scanners/[id] build unchanged in shape)
```

**7. Full backend suite summary**

First full run, taken **before** the alembic-head asserts were retargeted:

```
$ cd backend && uv run --extra dev pytest -q -p no:cacheprovider
=========================== short test summary info ===========================
FAILED tests/test_loop109_scanner_dsl.py::test_existing_seeded_scanners_still_compile
FAILED tests/test_loop113_sluglen.py::test_migration_068_chains_to_069 - Asse...
FAILED tests/test_loop114_sluglen.py::test_migration_069_single_head - Assert...
3 failed, 2224 passed, 30 skipped in 507.94s (0:08:27)
```

* The two `sluglen` failures were **mine** — migration 070 moved the alembic tip
  off `069_ident_text`, which both tests had frozen as a literal. Fixed in
  commit `test(loop116): prove executor wiring; retarget the alembic head
  asserts at 070`.
* `test_loop109_scanner_dsl.py::test_existing_seeded_scanners_still_compile` is
  **pre-existing on the base commit and not mine**: loop115 ("featured
  curation — flagship four") made featuring selective and set
  `is_featured: False` on `Election Edge Watch` and others, while this loop109
  test still asserts `entry.get("is_featured", True) is True` for every
  starter. It is untouched by this loop (I edited no scanner seeds and no
  compiler). It is **already fixed on integration** by
  `0eae298 test(loop116): drop stale all-featured assert (loop115 made
  featuring selective)`, so it is deliberately NOT duplicated here — fixing it
  again would only create a merge conflict.

Final full run, **after** the retarget:

```
$ cd backend && uv run --extra dev pytest -q -p no:cacheprovider
=========================== short test summary info ===========================
FAILED tests/test_loop109_scanner_dsl.py::test_existing_seeded_scanners_still_compile
1 failed, 2228 passed, 30 skipped in 420.38s (0:07:00)
```

**Zero failures attributable to loop116.** The single remaining failure is the
inherited loop115 one described above, already fixed on integration.

Run-to-run arithmetic: 2224 passed → 2228 passed = **+2** newly added executor
wiring tests (written after the first full run) **+2** recovered `sluglen` head
tests. Failures 3 → 1. `test_loop116_artifact.py` contributes 25 tests in total,
23 of which were already green in the first full run.

---

## Authz matrix deltas (orchestrator merges the counts)

`backend/tests/test_loop26_authz_matrix.py`:

| item | before | after |
|---|---|---|
| snapshot paths | 209 | **210** |
| operations | 230 | **231** |
| `public` | 115 | **116** |
| `admin` / `user` / `optional_user` / `admin_metrics` | 41 / 70 / 3 / 1 | unchanged |

New table entry:

```python
("get", "/api/v1/scanners/{scanner_id}/runs/{run_id}/artifact"): "public",
```

Classified `public` to match its sibling `("get", "/api/v1/scanners/{scanner_id}/runs")`,
which also uses `Depends(get_optional_user)` and is already labelled `public`.
Both classes share the same permitted-code set, so the label is cosmetic — but
consistency with the sibling matters more than pedantry here.

**Two parallel nodes also touch `main.py` and the authz counts.** My `main.py`
diff is exactly **one line in the include block** (`app.include_router(scanner_artifacts_router)`
at the end) plus one import line next to the existing `scanners` import. If the
count assertions conflict, the resolution is additive: **+1 path, +1 op, +1
public** on top of whatever the other nodes contribute.

---

## Charter compliance

| Rule | Status |
|---|---|
| `PAPER_TRADING_ONLY` untouched | ✅ (artifact stamps `paper_trading_only: true` in run_meta) |
| No order-path imports | ✅ AST-guarded by `test_artifact_service_never_imports_the_order_path` |
| NIM only via existing brief path + semaphore | ✅ `app.agents.analyst._LLM_SEMAPHORE`, `llm_route_analyst` |
| No secrets printed or set | ✅ |
| No push / no deploy | ✅ (5 local commits, nothing pushed) |
| No `git add -A` | ✅ (every commit staged path by path) |
| `scanners.py` router untouched | ✅ (parallel node owns it) |
| compile / clarify / convergence / alert email channels untouched | ✅ |
| `main.py` include-block diff | ✅ exactly one line |

Retries used: **0 of 2.** Strikes: **0 of 3.** No `ESCALATION.md`.
(The two `sluglen` failures were not a stuck error — they were the expected
downstream consequence of adding a migration, surfaced by the full suite and
fixed once.)

**AutoLab: not applicable** (one-shot capability build, no iterative measure).

---

## Commits

```
9944a48 feat(loop116): scanner run artifact service + artifact column (migration 070)
a7f9f78 feat(loop116): executor records the step funnel and stamps the run artifact
94fd406 feat(loop116): GET /scanners/{id}/runs/{run_id}/artifact
8108a20 test(loop116): artifact assembly, honest empty runs, paper-law filter, endpoint authz
af4ca40 feat(loop116): RunArtifact document on the scanner detail surface
<hash>  test(loop116): prove executor wiring; retarget the alembic head asserts at 070
<hash>  docs(loop116): STATE116-ARTIFACT
```

## Files touched

| File | Change |
|---|---|
| `backend/app/services/scanner_artifact_service.py` | new (≈700 lines) |
| `backend/app/api/v1/scanner_artifacts.py` | new |
| `backend/alembic/versions/070_scanner_run_artifact.py` | new |
| `backend/app/db/models.py` | +1 column on `ScannerRun` |
| `backend/app/services/scanner_executor_service.py` | +4 hunks (funnel + 2 attach calls) |
| `backend/app/main.py` | +1 import, +1 include line |
| `backend/tests/test_loop116_artifact.py` | new (25 tests) |
| `backend/tests/test_loop26_authz_matrix.py` | +1 route, 3 count bumps |
| `backend/tests/fixtures/openapi_snapshot.json` | regenerated (+9 lines) |
| `backend/tests/test_loop113_sluglen.py`, `test_loop114_sluglen.py` | head assert retargeted at 070 |
| `frontend/src/components/scanners/RunArtifact.tsx` | new |
| `frontend/src/components/scanners/ScannerDetailShell.tsx` | +1 import, +9 lines |
| `frontend/src/lib/scanners-api.ts` | +artifact types + `getRunArtifact()` |
| `frontend/e2e/scanners.spec.ts` | +1 assertion |
| `STATE116-ARTIFACT.md` | new |

Not touched, per charter: `backend/app/api/v1/scanners.py`, the compile /
clarify paths, convergence, and the alert email channels.
