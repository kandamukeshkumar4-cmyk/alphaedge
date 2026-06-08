---
id: phase-4-llm-nim
phase: 4
status: DONE
depends_on: [phase-3]
workflow: backend-feature
full_spec: docs/project/QUANT_ROADMAP.md  (§3 Phase 4)
---

# Phase 4 — NIM / LLM assist (narrow, non-decision)

**Objective:** put the LLM behind an OpenAI-compatible provider so NVIDIA NIM / Gemini / others are swappable. LLM only **matches, extracts features, and explains** — it NEVER decides a bet.

## Scope / files
- `backend/app/llm/provider.py` — OpenAI-compatible interface (`base_url` + key). Add `NIM_BASE_URL`/`NIM_API_KEY` + provider selector to `backend/app/core/config.py`.
- `backend/app/llm/resolution_matcher.py` — assist Phase 1 `matching.py` (structured verdict + rationale; the deterministic checks remain the gate).
- `backend/app/llm/news_features.py` — parse injury/news text → structured fields for Phase 3 `ml/features.py`.
- `backend/app/llm/explain.py` — explanations + risk notes; refactor `backend/app/agents/judge.py` onto `provider.py`.

## Acceptance gate
- Provider works against both NIM and Gemini request/response shapes (mocked in tests).
- `resolution_matcher` returns structured output consumed by `matching.py`.
- A **guard test asserts there is no code path where LLM output sets a stake, side, or `is_edge`.**
- `cd backend && uv run --extra dev pytest -q` + ruff green.

## Safety
LLM populates features/text only; deterministic checks remain the decision gate.

## PR line (filled)

```
Phase 4 llm-nim | gate=met | verify=pytest 267 collected, 265 passed, ruff clean
| safety=llm-non-decision asserted: ok (AST guard covers Assign+AugAssign+AnnAssign)
| review=manual | AutoLab=n/a
```

> Full paste-ready block: `docs/project/QUANT_ROADMAP.md` → §3 Phase 4.
