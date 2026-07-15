# loop-v41 — STATE

## A1 DIAGNOSIS (before any fix)

**Verdict: BOTH — keyless fallback AND intent-router miss.**

### Path traced
1. Frontend (`QuestMarketCard.tsx`) seeds:
   `Analyze ${title} for a paper trade. Current YES ~${pricePct}¢.`
   (Also: `Deep-dive …`, `Analyze live market …`.) Frontend intent is fine.
2. `POST /api/v1/assistant/chat` → `_llm_reply` → if no chat-route API key
   (`resolve_routed_endpoint` returns empty key; prod has `LLM_API_KEY` /
   `NIM_API_KEY` = `""`), calls `_build_deterministic_reply`.
3. Deterministic router matches keyword buckets only:
   odds/price/move | exposure/position | bear/downside | brief/analyst |
   trace/model/decision. **"analyze" / "deep-dive" / "paper trade" are absent.**
4. Prompt `"Analyze … Current YES ~54¢."` contains none of those tokens
   (has "¢" / "YES", not the word "price") → falls through to the canned
   capability menu (lines ~347–362).
5. Menu branch still appends `tools_used=["get_features"]` — matches the
   screenshot: get_features "succeeded", then menu text.

### Not the cause
- Frontend mis-send: no.
- LLM-present routing: `_llm_reply` skips keyword routing when a key exists
  and calls the chat client; A3 will confirm with a mock. Bug is keyless +
  router miss for the Analyze seed prompt.

### Fix direction (A2)
Add an analyze-intent branch that returns a real deterministic analysis from
existing read-only services (price/volume/24h move/drivers/brief/model vs
market). Menu only for unrecognized intents.

## LOOP LOG
| loop | date | result | proof |
|------|------|--------|-------|
| A1 | 2026-07-15 | DONE — both keyless + router miss | diagnosis above; no code change |

### ORCHESTRATOR REVIEW · A1 · 2871a97 · verdict: PASS
Both-cause diagnosis confirmed (router lacks an analyze bucket; the button's
own prompt falls through). A2: the analyze bucket must catch the exact seeded
prompts (Analyze/Deep-dive variants) and compose the full deterministic
analysis. Continue.
