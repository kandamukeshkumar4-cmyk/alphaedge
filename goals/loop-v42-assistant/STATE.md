# loop-v42-assistant — STATE

## LOOP LOG

| ticket | result | verifier notes / proof |
|---|---|---|
| M1 | DONE | Analyze now prefers the latest stored `PredictionLog`; when absent it invokes the existing `/markets/{slug}/prediction` pipeline behind the `leaderboard_cache` monotonic in-process cache with a 60-second TTL. Markets outside that pipeline state the honest clause: `Model probability: not available — this market is outside the prediction catalog.` No probability is fabricated. |
| M2 | DONE | Bear-case replies use only available signal drivers, stored 24h odds snapshots, catalog-volume percentile, and stored lock time. Missing drivers, snapshot pairs, catalog percentile, or lock time are explicitly omitted rather than inferred. |
| M3 | DONE | Authenticated market exposure reports existing paper positions, cost-basis concentration, and the exact adverse-resolution change to paper balance. The regression prompt `What would a resolution against my position do to my balance?` now routes to `get_exposure`, not bear-case. Language is descriptive; no recommendation or advice language was added. |
| M4 | DONE | Focused corrected suite: `44 passed in 11.77s`; `uv run --extra dev ruff check app tests`: `All checks passed!`. Earlier required full-suite observation: `1703 passed, 28 skipped in 286.96s`; it preceded the M3 intent-precedence correction. The corrected-HEAD full rerun was intentionally stopped by the orchestrator protocol request, so it is not represented as a final full-gate pass. Fresh pre-fix verifier: FAIL on the `against my position` routing bug; the regression test and precedence fix are committed. Never-rules confirmed by review: no order-path imports, no advice/recommendation language, no fabricated numbers, no weakened tests, no push, and no merge. |
