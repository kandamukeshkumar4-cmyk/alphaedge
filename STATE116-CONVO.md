# STATE116-CONVO — conversational alert authoring (audit gap #3)

**Branch:** `loop116-convo/node`  
**Worktree:** `E:/polymarket-worktrees/loop116-convo`  
**Date:** 2026-07-27  
**Seat:** executor (Cursor Grok 4.5 High)

## Mission

Close VIDEO-PARITY-AUDIT Tier-1 gap #3: scanner creation as a dialogue
(clarify → answer → ready → test fire → publish), not one-shot text→spec.

## What shipped

### Backend
- `scanner_compiler_service.py`: deterministic clarify state machine
  (`detect_clarification_kinds`, max 3 Qs/round, max 2 rounds → best-effort
  ready). In-process draft scratch (launch_limits pattern; no migration —
  alembic head remains `069_ident_text`). Delivery suggestions never promise
  email.
- `POST /api/v1/scanners/compile` extended: `{prompt, answers?, draft_id?}` →
  `ready | needs_clarification`. `text` kept as alias.
- `POST /api/v1/scanners/compile/testfire`: real executor `test_mode=True`,
  run persisted `is_test=true`. Scratch scanner `owner=__compile_draft__`
  (FK only; not listed/public). Publish remains `POST /scanners/`.

### Frontend
- `ScannerComposer`: chat transcript, clarify chips/inputs, Test fire preview,
  Publish. Honest in-app delivery copy.
- `scanners-api.ts`: conversational compile + testfire (+ mock parity).
- e2e: clarify → answer → ready → testfire. `skipOnboarding` now also seeds
  `ae_onboarded_v1` (orientation tour gate).

### Authz / OpenAPI
- `+1` public op: `POST /api/v1/scanners/compile/testfire`
- Snapshot paths **209 → 210**, ops **230 → 231**, public **115 → 116**
  (admin 41 / user 70 / optional_user 3 / admin_metrics 1 unchanged).
- Orchestrator note: if a parallel node also bumps these counts, rebase deltas.

## AutoLab

AutoLab: not applicable (no iterative measure — feature gap close).

## STOP — verification (verbatim)

### Targeted pytest
```text
$ cd backend && uv run --extra dev pytest -q tests/test_loop116_convo.py --tb=short
......                                                                   [100%]
6 passed in ~7–53s (cold/warm)
```

Named tests (all pass):
- `compile_missing_schedule_yields_schedule_question`
- `compile_vague_threshold_yields_threshold_question`
- `answers_roundtrip_reaches_ready`
- `two_rounds_max_then_best_effort_ready`
- `testfire_runs_real_executor_marked_test`
- `delivery_suggestions_never_promise_email`

### Ruff
```text
$ uv run --extra dev ruff check app/api/v1/scanners.py app/services/scanner_compiler_service.py app/schemas/scanners.py tests/test_loop116_convo.py
All checks passed!
```

### Alembic heads
```text
$ uv run --extra dev alembic heads
069_ident_text (head)
```
No migration added (in-process drafts). Parallel node may land `070*` — chain
on whatever `heads` shows at merge; this wave noted head stayed `069`.

### OpenAPI snapshot
```text
$ uv run --extra dev python scripts/regen_openapi_snapshot.py
wrote .../openapi_snapshot.json (210 paths)

$ uv run --extra dev pytest -q tests/test_loop26_authz_matrix.py::test_auth_class_table_covers_snapshot_surface tests/test_openapi_snapshot.py
.... passed
```

### Frontend
```text
$ cd frontend && npm run typecheck   # exit 0
$ npm run lint                       # exit 0 (eslint src --max-warnings=0)
$ npm run build                      # exit 0
$ npx vitest run src/lib/scanners-api.test.ts   # 4 passed
$ npx playwright test e2e/scanners.spec.ts --grep loop116
  ok … loop116 — clarify → answer → ready → testfire renders (24.0s)
  1 passed (56.3s)
```

### Full backend suite
(pasted below after run completes — see LOOP LOG)

## Guardrails

- `PAPER_TRADING_ONLY` untouched; no execution / order language.
- LLM never silently invents thresholds — asks.
- Delivery copy honest (in-app only).
- No secrets, no push/deploy, no `git add -A`.

## Out of charter (not touched)

- scanner_artifact_service / RunArtifact, convergence, email delivery,
  executor internals beyond `test_mode` flag.
