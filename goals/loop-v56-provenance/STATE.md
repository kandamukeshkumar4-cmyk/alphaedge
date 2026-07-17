# Loop V56 state — per-lock forecast provenance

Branch `loop56/lock-provenance`, based on `720d41a`. Not pushed, not merged —
the orchestrator merges and deploys.

## Gate (from `backend/`)

| command | result |
| --- | --- |
| `ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q` | **1755 passed, 28 skipped** in 260.68s |
| `uv run --extra dev ruff check app tests` | **All checks passed!** |

Counts checked from the summary line, not exit codes. Branch base `720d41a` is
1739 passed; the 16 new tests in `tests/test_loop56_lock_provenance.py` account
for the whole delta (1739 + 16 = 1755). No pre-existing test was changed,
skipped, or weakened.

Migration revision id: **`048_lock_provenance`** (19 chars, under the
varchar(32) limit). `ScriptDirectory.get_heads()` reports a single head,
`down_revision = "047_social"`.

## Tickets

| id | status | evidence |
| --- | --- | --- |
| P1 | DONE | `048_lock_provenance` adds 5 nullable columns to `forecast_logs`; single alembic head verified; ORM columns added. |
| P2 | DONE (amended — see finding) | Provenance written by the same INSERT as the lock, autolock included. Records the *producing path*, not `ML_MODEL_TYPE`. |
| P3 | DONE | `population_summary` reports `provenanced_count` + `provenance_cutoff`; `ab_harness` `model_type_history` discloses the cutoff. `ab_ready` unchanged. |
| P4 | DONE | 16 tests: atomicity, null-registry honesty, historic rows, cutoff detection, tie case, FIFA routing. Mutation-checked (below). |

## Verifier (separate fresh-context agent, adversarial)

Verdict **FAIL → resolved**. It independently re-ran the gate and reproduced the
counts, and independently re-derived the passthrough finding from the code
(its own probe: `0.37 → 0.37`, `0.62 → 0.62`, `0.9 → 0.9`), ruling the P2
deviation **JUSTIFIED, not rationalization**.

Its blocking defect was real and mine: **`tests/test_loop56_lock_provenance.py`
was never committed** — the P4 tests existed only as an untracked working file,
so the branch would have shipped P1–P3 with zero provenance tests and a real
count of 1739, while STATE.md claimed P4 DONE. Fixed by this commit; that claim
was an overclaim until now.

Two MINOR findings, both addressed rather than waved off:
- Cutoff docstring overstated the tie case (an unprovenanced row can share the
  cutoff's `locked_at`). The behavior was already sound — `eligible` is computed
  from the provenanced suffix, not a timestamp re-filter — but the docstring is
  now precise and `test_tied_lock_times_never_readmit_an_unprovenanced_row` pins
  it. Mutation-checked: the naive `locked_at >= cutoff` filter fails that test.
- `PRODUCER_FIFA` was unasserted; `test_fifa_route_is_attributed_to_the_fifa_model`
  now covers it, including that `replace()` preserves the routed prediction.

It also ran a differential test of `predictor.py` against `720d41a` (72 generic
+ 9 FIFA cases, every field but `producer`): **0 diffs** — the refactor changes
no forecast value. Independently confirmed `ab_ready` untouched, no
`UPDATE`/`op.execute` anywhere (no backfill), order path absent from the diff,
and that STATE.md's migration-coverage limit is honest.

## ⚠ FINDING — the premise of P2 is false: no model produces locked forecasts

**This is the most important output of V56 and it changes what V51/Q2 means.**

`ForecastService.predict` hands `predict_market` exactly
`{market_slug, implied_yes, market_implied}`. `_artifact_probability` requires
`model_artifact_path` + `calibrator_path` + `feature_columns` together; with none
supplied it returns `None`, and `predicted` falls back through
`("model_probability", "calibrated_probability", "predicted_prob")` to **`implied`**.

Measured, not inferred (`ForecastService.predict`, real code, this worktree):

```
implied=0.37 -> model_prob=0.37 passthrough=True
implied=0.62 -> model_prob=0.62 passthrough=True
implied=0.90 -> model_prob=0.90 passthrough=True
```

`grep` confirms **no production caller ever passes an artifact path**: all three
callers of `ForecastService.predict` (`forecast_autolock.py`, `market_detail.py`,
`admin_markets.py`) pass slug + implied only. The `ModelVersion` registry is
entirely disconnected from the lock path. Every autolocked "model forecast" is
the venue's own price, arithmetically identical.

**Consequence for the work order.** P2 says to write "current `ML_MODEL_TYPE`" and
"artifact identifier/digest from the registry". Doing that literally would stamp
`model_type="xgboost"` onto rows that no XGBoost ever touched — fabricated
provenance, the exact defect V56 exists to prevent, and a direct breach of the
work order's own "never fabricate" rule. Worse, it would make a future A/B read a
clean "provenance-constant xgboost population" and trust rows that contain zero
model signal.

**What was implemented instead.** The predictor now reports which path produced
the number (`PRODUCER_ARTIFACT` / `PRODUCER_FIFA` / `PRODUCER_SUPPLIED` /
`PRODUCER_IMPLIED_PASSTHROUGH`) and the lock records that. Today every autolock
honestly records `model_type="implied_passthrough"`, `artifact_digest=NULL`,
`model_version=NULL`, plus the real `feature_payload` and a `feature_schema_digest`
over the feature names. The null digest is explicitly sanctioned by the work order
("store null and count it") and is counted as `missing_artifact_digest_count`.

**For the orchestrator to decide (NOT fixed here — out of scope, listed not
touched):** the accruing population cannot answer the model-selection question no
matter how long it accrues, because the locked probability *is* the market price.
Wiring the registry artifact into the lock path is a separate loop with real
forecast-changing consequences. V56 makes this permanently visible in the data
rather than papering over it.

## Definitions worth pinning

- **provenanced row** = `model_type IS NOT NULL` (the producer is recorded).
  `artifact_digest` is deliberately *not* required — requiring it would report
  zero forever and hide the `model_type` signal §C-7 actually asks for.
- **`provenance_cutoff`** = `locked_at` of the earliest lock from which *every*
  later lock is provenanced (an unbroken suffix; a gap resets it). Rows at/after
  it are eligible for the provenance-constant check.

## Guardrails held

- Order path (`RiskService -> OrderIntent -> OrderBookService`) untouched — no
  file in it was opened for edit.
- `PAPER_TRADING_ONLY` untouched.
- No backfill: historic rows keep NULL provenance, asserted by
  `test_lock_without_provenance_keeps_every_column_null`.
- No post-close data: provenance is captured pre-lock, from the payload actually
  sent to the predictor.
- No push, no merge.
- `ab_ready` behavior unchanged; clusters still gate.

## Honest limits of this evidence

- **The migration is not exercised by pytest.** `tests/conftest.py` builds the
  schema with `Base.metadata.create_all` on in-memory SQLite, so `048`'s
  `upgrade()`/`downgrade()` are validated only by alembic's script walk (single
  head, correct `down_revision`) — not by running against Postgres. A real
  `alembic upgrade head` against a Postgres instance is still unproven and should
  run in the deploy wave. Docker was not started for this loop.
- No production verification: `scripts/verify_prod.py` was not run — this loop
  is not deploy-affecting on its own and the orchestrator owns the deploy.
- `provenanced_count` will read 0 until locks made after this migration resolve
  and get scored. That is correct, not a bug.

## Doc references in the work order that do not exist

`goals/loop-v51-ab-retarget/PLAN.md` (Revision 2, Q1/Q2), the RUNBOOK's
"DECISION RECORD", `§C-1a`, and `§B-6` are not in this worktree and not in any
commit (`git log --all` finds no PLAN.md; no file contains "DECISION RECORD").
Used the real equivalents instead: RUNBOOK `§C-1`, `§C-7` (which explicitly asks
for this ticket — "record the producing model version on each locked forecast —
cheap now, impossible retroactively"), `§B-5`, and
`goals/loop-v51-ab-retarget/{GOAL,STATE}.md`. `ab_harness.py` cites "§B-6" in a
comment, so the RUNBOOK section numbering may have drifted from its citations.

## LOOP LOG

| date | status | evidence |
| --- | --- | --- |
| 2026-07-17 | P1-P4 DONE | Gate: backend **1755 passed / 28 skipped**; ruff `app tests` clean. Migration `048_lock_provenance`, single head on `047_social`. Fabrication mutation (`model_type="xgboost"`, `artifact_digest="sha256:deadbeef"`) caught by 3 tests; naive-cutoff-filter mutation caught by 1; all reverted, verified with `git diff --quiet`. Verifier independently reproduced the counts and the passthrough finding; its blocking catch (P4 tests uncommitted) is fixed. |

AutoLab: not applicable (no iterative measure — schema/provenance correctness,
not a metric to improve).
