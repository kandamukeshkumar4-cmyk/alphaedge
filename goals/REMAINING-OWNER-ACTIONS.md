# Remaining Owner Actions

> Everything that agents can build has shipped. This file lists ONLY the items
> that no agent can perform — they require owner credentials, owner-only infra
> access, or real-world data that does not yet exist. Each has an explicit
> unblock condition.

## 1. Push / merge the loop commits and trigger the HF Space deploy — ✅ DONE (2026-07-07)
Loop2–loop9 merged to `codex/alphaedge-base` (PRs #49/#50/#51) and the
**"Deploy Backend to HF Space"** workflow ran green through every smoke gate
(health, markets, snapshot, admin agent-proof, paper-order lifecycle, smoke
suite). Live: https://mukeshkumar007-alphaedge-api.hf.space/health

## 2. Factory-reboot the HF Space if Loop 8 found it stale — ✅ NOT NEEDED (2026-07-07)
Every deploy reached `RUNNING` on the pushed revision (the workflow's
wait-for-revision step passed); the Space was never stuck on a stale image. No
factory reboot was required. (Still owner-only if a future deploy hangs.)

## 3. Make the deployed LLM path return `generator=llm` — ✅ DONE (2026-07-07)
**Live in production.** Both the analyst briefs and the assistant chat now
return real LLM output on the deployed Space.
- Deploy-workflow bug fixed + shipped (PR #50): per-use-case model keys
  (`LLM_MODEL_ANALYST`/`_CHAT`/`_ANALYST_DEEP`) were never in the secret-sync
  list, so the analyst called the placeholder default `z-ai/glm-5.2` (not a real
  NIM id) and silently fell back.
- **Actual root cause (found by owner):** it was never egress or a bad key — it
  was the model ids. Tested directly against NVIDIA with the working NIM key:
  `qwen/qwen2.5-7b-instruct` → 404 (doesn't exist on this key);
  `qwen/qwen3-next-80b-a3b-instruct` (local `.env` model) → >60s timeout, too
  slow/cold for the analyst path; **`meta/llama-3.1-70b-instruct` → works,
  responds instantly.**
- **Fix applied by owner:** set `LLM_MODEL`, `LLM_MODEL_ANALYST`,
  `LLM_MODEL_CHAT` = `meta/llama-3.1-70b-instruct`, synced the verified
  `NIM_API_KEY` + `LLM_PROVIDER=nim`, re-ran the deploy with
  `sync_runtime_secrets=true`.
- **Live-verified:** the deploy's AI-mode check now prints
  "AI analysis is live (generator=llm)" (previously always warned `fallback`); a
  fresh analyst run returns `generator: llm` with a real LLM headline; the
  assistant chat returns a genuine LLM answer with the paper-trading-only banner
  intact.
- **Security note:** the working `NIM_API_KEY` lives in plaintext in
  `backend/.env`, which is untracked (not in git) — keep it that way; never
  commit it.
- **Optional enrichment, still owner-held:** `EXA_API_KEY` (news citations) and
  `FRED_API_KEY` (macro) remain unset; they enrich briefs but are not required
  for `generator=llm`.

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
