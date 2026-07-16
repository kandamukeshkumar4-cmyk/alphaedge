# Loop V52 — Nemotron-3 reasoning signal (NIM) + Ralph-loop AutoLab runner

Reference: togethercomputer/together-cookbook `Agents/Nemotron3Ultra_RalphLoop`
(Ralph pattern: `while not done: fresh_agent(same_task)` with filesystem memory
— PROGRESS.md per iteration, DONE.md as the stop signal).

## Outcome
The forecasting pipeline gains an optional LLM reasoning signal powered by
NVIDIA Nemotron-3 via the existing NIM provider config, plus an offline
Ralph-style AutoLab runner that iteratively improves the signal's prompt
against measured Brier — WITHOUT touching the calibrated GBDT forecaster's
honesty guarantees.

## Hard constraints (binding, from AGENTS.md + V40 runbook)
- The LLM NEVER emits the forecast probability. It emits a structured signal
  (direction, strength 0-1, rationale, cited inputs) that enters the
  prediction graph as ONE input, exactly like news_signal.
- Pre-close inputs only (leakage gate): the signal may see market title,
  category, current/past prices, and the news_signal summary — never
  resolution info or post-close data. Record signal payload + model id +
  prompt version with the forecast (provenance).
- Flag-gated: NEMOTRON_SIGNAL_ENABLED (default false). Missing NIM_API_KEY =
  graceful skip with a logged reason, never a crash, never a fabricated
  signal.
- No order-path changes; PAPER_TRADING_ONLY untouched; assistant remains
  analysis-only. Never game the benchmark.

## Tickets
- N1 `app/signals/nemotron_signal.py`: NIM chat-completions call (reuse
  nim_base_url/nim_api_key from config; model name via new setting
  NEMOTRON_MODEL, default the current free NIM Nemotron-3 id — VERIFY the
  exact id at https://build.nvidia.com before hardcoding; do not guess).
  Strict JSON schema output with validation + one retry; per-market cache
  (follow news_signal caching); timeout + circuit breaker.
- N2 Wire a nemotron_node into the prediction graph beside news_node,
  feeding a bounded feature (e.g. signed strength in [-1,1]); off when flag
  off; provenance recorded per V51 amendment expectations.
- N3 `backend/scripts/ralph_signal_lab.py`: offline Ralph-loop runner —
  fresh iteration each cycle, workspace dir with PROGRESS.md / DONE.md,
  benchmark = Brier over resolved forecast_scores rows (cluster-aware count
  disclosed), budget + K=3 no-progress stop per the AutoLab skill. Prompt
  variants are versioned files; the runner NEVER writes to prod tables.
- N4 Tests (mock NIM; flag off/on; missing-key skip; leakage guard: a
  post-close field in the payload is a hard test failure) + full gate:
  ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q (CHECK COUNTS)
  and uv run --extra dev ruff check app tests.

## Completion
All tickets DONE in STATE.md with gate counts, AutoLab line included
(N3 provides the iterative measure). BLOCKED with reasoning if the free NIM
model id cannot be verified or the API shape differs.
