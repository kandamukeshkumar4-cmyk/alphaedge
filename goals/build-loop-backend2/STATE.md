# Backend Loop 2 — quality + intelligence (started 2026-07-04)

Goal: kill the remaining user-facing reliability bugs and make the AI layer
cite real external evidence end-to-end, now that NIM + Exa keys are live.

Method: AutoLab persistence loop per ticket (baseline gate → benchmark →
measure/edit/re-measure). Maker/checker: each ticket live-verified before DONE.
Guardrails: PAPER_TRADING_ONLY, no LLM order path, never game a benchmark.

| # | Ticket | Status | Benchmark | Notes |
|---|--------|--------|-----------|-------|
| B01 | Markets-list micro-cache (kill self-inflicted 429s) | PENDING | 0 429s on /api/v1/markets under homepage load | rails poll dozens/sec; 2-5s TTL in-process cache |
| B02 | Weather forecast-vs-actual logging (learned sigma bootstrap) | QUEUED | rows accumulate nightly | AruneshDev idea; needs weeks of data before sigma learning |
| B03 | Weather edges → SignalEvents + feed | QUEUED | weather edge visible in /signals + ticker | today API/page-only |
| B04 | Exa news → news_arrival SignalEvents → analyst citations | PENDING | brief cites kind=news with real Exa headline | closes the "0 news" gap in briefs |
| B05 | Deep daily digest on reasoning model | QUEUED | digest uses LLM_MODEL_DEEP (nemotron-49b, ~19s ok for cron) | per-feature model routing |
| B06 | Expiry-fade + momentum screeners (signals only) | QUEUED | deterministic screener API + tests | CloddsBot-inspired, clean-room |
| B07 | Batch Kalshi catalog ingest (429s in sync_open_events) | PENDING | ingest cycle completes with <5 429s | tick loop fixed; ingest still per-event calls |

## AutoLab log
- 2026-07-04 bootstrap: baseline = 1044+ backend tests green, ruff clean,
  NIM+Exa live-verified. Loop authored.
