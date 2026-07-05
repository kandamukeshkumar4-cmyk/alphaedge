# Plan 008: Retire or document stale `hf_stage/` tree

> **Executor instructions**: This is mostly docs + CI guard. Do not delete without confirming HF deploy path.
> Update `plans/README.md` when done.
>
> **Drift check**: `git diff --stat 24fa35f..HEAD -- hf_stage/ .github/workflows/`

## Status

- **Priority**: P3
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `24fa35f`, 2026-06-12

## Why this matters

`hf_stage/` is a ~260-file copy of `backend/` **without** live mirror modules (`live_market_ingest.py`, `kalshi_live_ingest.py`, `run_live_tick_once`). Agents and humans can edit the wrong tree. Azure production uses `backend/` via `scripts/deploy_azure_live.ps1`; HF workflow copies `backend/` at build time (`.github/workflows/deploy-hf-space.yml` L151–152) — `hf_stage/` is not the deploy source.

## Current state

- `hf_stage/app/workers/price_feed_worker.py`: catalog-only, no live tick
- No `hf_stage/app/services/live_market_ingest.py`
- Duplicate tests: `hf_stage/tests/test_deploy_config.py`, `backend/tests/test_deploy_config.py`
- `deploy-azure-live-summary.txt`: production is Azure Container Apps + SWA

## Scope

**In scope**
- `hf_stage/README.md` (create or update) — "STALE MIRROR — do not edit; canonical code is `backend/`"
- Root `README.md` or `docs/deploy.md` — single source of truth table (Azure vs HF)
- Optional: delete `hf_stage/` if operator confirms HF Space unused — **default: document only, do not delete**

**Out of scope**
- Changing Azure deploy
- Merging hf_stage into backend

## Steps

### Step 1: Confirm deploy paths

Read `.github/workflows/deploy-hf-space.yml` and `scripts/deploy_azure_live.ps1`. Document which directory each uses.

### Step 2: Add `hf_stage/README.md`

```markdown
# STALE — do not implement features here

Canonical API: `../backend/`
Azure deploy: `scripts/deploy_azure_live.ps1`
HF Space workflow copies `backend/` at CI time.
```

### Step 3: CI guard (optional)

Add a script or test that fails if `hf_stage/app` differs from `backend/app` for critical live files — or mark `hf_stage` deprecated in `AGENTS.md` one paragraph.

**Verify**: No code behavior change; docs readable

## STOP conditions

- HF Space production still runs code only from `hf_stage/` (would need sync instead of delete)
- Deletion requested without user confirmation

## Done criteria

- [ ] Clear doc: where to edit for live mirror
- [ ] `plans/README.md` row 008 → DONE
- [ ] No accidental deletion of HF deploy path without sign-off
