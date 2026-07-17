# loop-v52-nemotron-signal — STATE

## Status
**N1–N4 DONE** (2026-07-16)

## Model id verification
- **Verified** free NIM Nemotron-3 id from official NVIDIA build.nvidia.com:
  `nvidia/nemotron-3-nano-30b-a3b`
  (https://build.nvidia.com/nvidia/nemotron-3-nano-30b-a3b — free API endpoint;
  OpenAI-compatible model string matches repo pattern used by
  `LLM_MODEL_ANALYST_DEEP` for ultra: `nvidia/nemotron-3-*`).
- Super/Ultra free endpoints also exist; Nano chosen as default free reasoning
  signal model (override via `NEMOTRON_MODEL`).
- Assumption: none required for model id (verified). API shape = standard
  OpenAI chat.completions against `NIM_BASE_URL` (already in config).

## LOOP LOG
| ticket | date | result | proof |
|--------|------|--------|-------|
| N1 | 2026-07-16 | DONE | `feat(loop52): N1 nemotron_signal NIM chat + cache + circuit breaker` — flag-gated, strict JSON + retry, leakage gate, cache, circuit breaker; never emits probability |
| N2 | 2026-07-16 | DONE | `feat(loop52): N2 wire nemotron_node into prediction graph` — node after news, bounded `nemotron_signed_strength` ∈ [-1,1], provenance (model_id, prompt_version, payload) |
| N3 | 2026-07-16 | DONE | `feat(loop52): N3 ralph_signal_lab offline AutoLab runner` — PROGRESS.md/DONE.md workspace, Brier research proxy, K=3, never writes prod |
| N4 | 2026-07-16 | DONE | `feat(loop52): N4 tests + gate` — mock NIM; flag/key/leakage; full pytest + ruff |

## Gate (paste)
```
uv run --extra dev ruff check app tests
All checks passed!

ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q
1743 passed, 28 skipped in 258.25s (0:04:18)
```

## Guardrails
- LLM never emits forecast probability (signal only)
- Pre-close inputs only; post-close field in payload = hard test failure
- `NEMOTRON_SIGNAL_ENABLED` default false; missing `NIM_API_KEY` = graceful skip
- No order-path changes; `PAPER_TRADING_ONLY` untouched
- No push/merge

## AutoLab
AutoLab: baseline=brier=0.271919 (fixture research proxy) | benchmark=research_proxy_brier_on_fixture (ralph_signal_lab) | iterations=6 best=0.270821 prompt=v1_conservative | budget=6/6 | outcome=improved
