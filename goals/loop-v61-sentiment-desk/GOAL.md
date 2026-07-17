# Loop V61 — Continuous sentiment desk (QUEUED — first free backend runner)

Reference (READ ONLY, E:/polymarket-reference/): TradingAgents (analyst-debate
structure), DeepEar (news -> quant scores), TradeAgent (sentiment trend
tracking), fsaavedra bot. Extract techniques, cite, never vendor.

## Outcome
News/sentiment goes from hourly snapshot to a CONTINUOUS desk: high-frequency
re-checks on markets near close or with fresh signal, sentiment TREND (not
just level), and a multi-lens analyst pass that the prediction graph and pods
consume.

## Tickets
- S1 Adaptive cadence: news_signal refresh driven by urgency (close_at
  proximity, price-jump events, whale spikes from V58) — 5-15min for hot
  markets, hourly baseline; budget-capped calls; circuit breaker.
- S2 Sentiment trend: persist per-market sentiment time series; expose
  direction + acceleration as bounded features (leakage gate: capture
  timestamps, pre-close only).
- S3 Analyst-debate pass (flag-gated, NIM): for hot markets, three cheap
  lenses (news bull case, news bear case, base-rate skeptic) -> structured
  verdict; store all three with provenance; feeds Nemotron/master context,
  never emits the probability itself.
- S4 Wire into master context endpoint (V58) + pod scoring inputs (V57
  interfaces read-only).
- S5 Tests + full gate (CHECK COUNTS; ruff). Migration 052+ if needed
  (<=32 chars). STATE.md with counts.

Constraints: paper-only, order path untouched, no fabricated sentiment, no
social scraping that violates ToS (public APIs only; X/Reddit only if a
compliant source is available — otherwise document the gap honestly).
Never push/merge.
