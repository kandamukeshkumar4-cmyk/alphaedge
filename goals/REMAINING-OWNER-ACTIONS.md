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

## 3. Make the deployed LLM path actually return `generator=llm`
Progress (2026-07-07, agent): `LLM_PROVIDER=nim`, `NIM_API_KEY`, `LLM_MODEL`,
`LLM_MODEL_ANALYST`, `LLM_MODEL_CHAT` are now all set as GitHub secrets and
**verified synced to the Space** (deploy log: "Synced HF Space runtime secrets:
… LLM_PROVIDER, LLM_MODEL, LLM_MODEL_CHAT, LLM_MODEL_ANALYST, NIM_API_KEY").
A real deploy-workflow bug was fixed and shipped: per-use-case model keys were
never in the sync list, so the analyst used the placeholder default
`z-ai/glm-5.2` (not a real NIM id) → PR #50, merged.

**Still blocked (owner-only diagnosis).** Even after syncing real models
(`meta/llama-3.1-70b-instruct`, then `qwen/qwen2.5-7b-instruct`), BOTH the
analyst brief and the assistant chat still return the deterministic fallback on
the live Space — i.e. every NIM call fails at runtime, independent of model and
endpoint. The exception is swallowed by the analyst/assistant `except` and only
written to the **Space server logs**, which need owner HF access to read.
- **Root cause is one of:** (a) HF Space egress to `integrate.api.nvidia.com`
  blocked, or (b) `NIM_API_KEY` invalid / quota-exhausted in the deployed env.
- **Owner unblock steps:** open the Space logs and find the
  `analyst LLM write_brief failed (provider=nim model=…)` WARNING to see the real
  error; verify the NIM key has quota and the exact model id it can access (the
  local run that worked used a "NIM qwen" model — confirm which one); if egress
  is the issue, allow outbound to the NIM host. Then re-run "Deploy Backend to HF
  Space" with `sync_runtime_secrets=true`.
- **Verified done when:** `POST /api/v1/analyst/run?market_slug=<real market>`
  returns `generator=llm` (and the market-prediction endpoint reports
  `n_models >= 1`).
- **Optional enrichment, owner-held values:** `EXA_API_KEY` (news citations) and
  `FRED_API_KEY` (macro) are not set; they improve briefs but do not block
  `generator=llm`.

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
