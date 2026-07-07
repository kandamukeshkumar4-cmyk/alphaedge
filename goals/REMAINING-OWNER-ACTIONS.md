# Remaining Owner Actions

> Everything that agents can build has shipped. This file lists ONLY the items
> that no agent can perform — they require owner credentials, owner-only infra
> access, or real-world data that does not yet exist. Each has an explicit
> unblock condition.

## 1. Push / merge the loop commits and trigger the HF Space deploy
Agents do not push to `origin` or dispatch deploys. Owner must push/merge the
loop branches and run **"Deploy Backend to HF Space"**.
- **Unblock condition:** loop commits merged to the deploy branch and the deploy
  workflow completes green.

## 2. Factory-reboot the HF Space if Loop 8 found it stale
Free-tier Spaces sleep and can serve a stale build; only the owner can factory
reboot from the Space settings.
- **Unblock condition:** Space rebooted and `/health` returns 200 on the fresh
  build (recheck after the Loop 8 smoke result).

## 3. Sync LLM / NIM / EXA / FRED secrets to the Space
The deploy workflow can sync runtime secrets, but the secret values themselves
are owner-held (`LLM_PROVIDER`, `NIM_API_KEY`, `LLM_MODEL`, `LLM_MODEL_DEEP`,
`EXA_API_KEY`, `FRED_API_KEY`).
- **Unblock condition:** deployed research briefs return `generator=llm` and
  `n_models >= 1` (i.e. real LLM path, not deterministic fallback).

## 4. LightGBM vs XGBoost A/B on real resolved outcomes
Cannot be run until enough markets have resolved to make walk-forward Brier
meaningful. Flip `ML_MODEL_TYPE` default ONLY if LightGBM measurably wins.
- **Unblock condition:** ~100 resolved outcomes exist in the prod DB
  (~17 as of 2026-07-03); record both Briers regardless of outcome.

## 5. Enable `INSTABILITY_FEATURE_ENABLED`
The instability feature is gated off because no election dataset exists to
validate it.
- **Unblock condition:** an election dataset is available; enable the flag only
  after the feature is validated against it.

## 6. Chrome extension track — frozen by owner decision
The `extension/` track is intentionally out of scope. No agent will develop,
package, or document it further.
- **Unblock condition:** owner explicitly un-freezes the track.
