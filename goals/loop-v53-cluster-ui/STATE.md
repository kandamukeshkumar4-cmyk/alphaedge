# Loop V53 — Cluster-gate transparency UI

Scope: frontend-only transparency for the resolved-count A/B readout. No order or trade components, no push or merge.

Baseline: the production resolved-count endpoint returned a hosting-provider error on 2026-07-17; the checked-in backend contract in `backend/app/ml/ab_harness.py` is the source of truth for this loop.

| Ticket | Status | Proof / note |
| --- | --- | --- |
| U1 | DONE | New top-level/nested contract types and guarded cluster progress compatibility added. Focused Vitest and TypeScript verification are deferred to U4 because frontend `node_modules` is absent. |
| U2 | DONE | `/eval` and the shared home A/B summary now use correlation clusters / cluster threshold, keep nominal scored forecasts secondary, and display only a raw `CONCENTRATED` verdict verbatim. |
| U3 | PENDING | — |
| U4 | PENDING | — |
