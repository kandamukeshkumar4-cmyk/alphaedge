# Escalation: backend pytest gate timeout — RESOLVED

Date opened: 2026-07-14
Date resolved: 2026-07-14

## Original blocker

`py -3.13 orchestration/gate.py` failed with `FAIL backend pytest: timed out`
(1,800s limit). The suite needed ~60 minutes end to end.

## Root cause (profiled, not guessed)

`tests/test_fifa_model.py::test_predictor_calibrated_prob_for_canonical_match`
alone took **2,956s (49 min)**: with a cold `.model_cache.pkl`, `FifaPredictor`
trains on ~14.6k historical matches, and `build_training_dataset` called
`compute_team_stats` per match, each call doing pandas `iterrows()` over the
full 49k-row frame — an O(n²) scan. The 500-run Monte Carlo re-predicted
identical match-ups without memoization. This was also a production cold-start
hazard, not just a test problem.

## Fix (behavior-preserving, verified equivalent)

- `app/data/fifa/features.py`: `compute_team_stats` vectorized via a
  `PreparedResults` numpy view (per-team row indices, score arrays, UTC-ns
  dates, WC flags). An old-vs-new comparison on real data showed **0 mismatches**
  across all TeamStats fields, including NaN-score and h2h edge cases.
- `app/data/fifa/model.py`: `build_training_dataset` prepares arrays once;
  `predict_match` accepts an optional `prepared=` view.
- `app/data/fifa/predictor.py`: Monte Carlo `predict_fn` memoized
  (deterministic per match-up) and shares one prepared view.

Cold predictor init: **2,957s → 110s (27×)**; identical output probability
(0.5802) for the canonical market.

Two pre-existing timing flakes surfaced by full-gate runs were also fixed:

- `app/workers/daily_digest.py`: digest dedupe now keys on the day-stamped
  title instead of a `created_at` wall-clock window (which also never deduped
  backfilled days).
- `app/api/v1/assistant.py` + `tests/test_assistant_chat.py`: anon rate-limiter
  clock made injectable; the test pins it so slow CI runs can't straddle the
  60s window.

## Verification

`py -3.13 orchestration/gate.py` exit 0:
backend pytest 1570 passed, 28 skipped, 2 xfailed in 1,036s; ruff pass;
frontend typecheck/tests (381)/build pass.

---

# Loop V57 P1 escalation: migration-chain mismatch — RESOLVED

## Trigger

The binding P1 constraint requires the pods migration to be `049+` on the
head `048_lock_provenance`, but that head is absent from the requested branch.
This is a schema-history decision: choosing a different parent or synthesizing
the missing migration would change the database upgrade contract.

## Original evidence

- Current branch: `loop57/pod-engine` at
  `a538d137e6e620044bec85d24255861883cac682`.
- Checked versions end at `047_social.py`; no `048_lock_provenance.py` exists
  in this checkout.
- `048_lock_provenance.py` exists in commit
  `f58a1c160fbc080619d749c70dcb3eee8eab2dfa`, whose `down_revision` is
  `047_social`.
- `git merge-base --is-ancestor f58a1c1 HEAD` exits `1`; that commit is not in
  the branch history.

## Resolution

The established loop56 `048_lock_provenance` history is now merged into this
branch by `133af64` (`merge: integrate 048_lock_provenance head`). Verified in
this checkout with `ls backend/alembic/versions`: `048_lock_provenance.py` is
present. The binding orchestrator note supersedes the original proposed 049
name: V57 now creates `053_pods` with the locally consistent temporary
`down_revision = "048_lock_provenance"`; the orchestrator will re-chain it
above 052 at integration time.

No replacement 048 or alternate migration parent was created.
