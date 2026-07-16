# Loop V51 — A/B harness retarget (QUEUED; constitution = V40 RUNBOOK)
> Runner: TBD (first free backend runner). Read goals/loop-v40-accuracy-prep/
> RUNBOOK.md FIRST — it is binding, especially §B-3 (split rule) and the
> exit criteria. Orchestrator decision C-1: the 100-gate governs the
> forecast_scores population; the legacy snapshot-matrix A/B input is
> deprecated for the accuracy loop.
## Tickets (feat(loop51): <ticket>)
- R1 Data query: forecast_scores x external_markets returning
  locked_at + resolved_at (NOT scored_at) + category + market identity.
- R2 Split engine per §B-3: train resolved_at < T_eval_min, eval
  locked_at >= T_eval_min, embargo window; concentration checks (category
  + repeated-question effective-n) computed and reported.
- R3 ab_ready realignment: gate on forecast_scored_count + concentration
  thresholds from the runbook (additive fields; no silent semantic swap —
  document old vs new in the response).
- R4 Preflight hard-asserts: ML_MODEL_TYPE constant across the window;
  lightgbm importable in THIS runtime else REFUSE (no fallback-vs-itself);
  E06 honest-outcome codified (concentrated => both Briers, no winner).
- R5 Tests + full gate + verifier. NEVER train on post-close info. STOP.
