# Backend Loop 2 — quality + intelligence (started 2026-07-04)

Goal: kill the remaining user-facing reliability bugs and make the AI layer
cite real external evidence end-to-end, now that NIM + Exa keys are live.

Method: AutoLab persistence loop per ticket (baseline gate → benchmark →
measure/edit/re-measure). Maker/checker: each ticket live-verified before DONE.
Guardrails: PAPER_TRADING_ONLY, no LLM order path, never game a benchmark.

| # | Ticket | Status | Benchmark | Notes |
|---|--------|--------|-----------|-------|
| B01 | Markets-list micro-cache (kill self-inflicted 429s) | DONE | 0 429s on /api/v1/markets under homepage load | rails poll dozens/sec; 2-5s TTL in-process cache |
| B02 | Weather forecast-vs-actual logging (learned sigma bootstrap) | QUEUED | rows accumulate nightly | AruneshDev idea; needs weeks of data before sigma learning |
| B03 | Weather edges → SignalEvents + feed | QUEUED | weather edge visible in /signals + ticker | today API/page-only |
| B04 | Exa news → news_arrival SignalEvents → analyst citations | DONE | brief cites kind=news with real Exa headline | closes the "0 news" gap in briefs |
| B05 | Deep daily digest on reasoning model | QUEUED | digest uses LLM_MODEL_DEEP (nemotron-49b, ~19s ok for cron) | per-feature model routing |
| B06 | Expiry-fade + momentum screeners (signals only) | QUEUED | deterministic screener API + tests | CloddsBot-inspired, clean-room |
| B07 | Batch Kalshi catalog ingest (429s in sync_open_events) | DONE | ingest cycle completes with <5 429s | tick loop fixed; ingest still per-event calls |
| B08 | Demo reliability: E2E smoke harness + deployed-AI root cause | DONE 2026-07-05 | 15-test user-journey smoke green vs live stack | See AutoLab log. Root causes of "demo broken": (1) deploy workflow never synced LLM/NIM keys to the HF Space → deployed briefs/chat always deterministic fallback; (2) assistant gated on LLM_API_KEY only, ignoring NIM_API_KEY even when set; (3) nothing pinged the free-tier Space/Neon between deploys → asleep at demo time. Fixes: provider-aware assistant gate + regression tests; optional AI-key sync in deploy-hf-space.yml; demo-uptime.yml 30-min keep-alive/uptime cron; tests/smoke/test_user_journey.py (any --base-url) + scripts/run_smoke.sh; analyst LLM failures now log at WARNING with provider/model. |

## AutoLab log
- 2026-07-04 bootstrap: baseline = 1044+ backend tests green, ruff clean,
  NIM+Exa live-verified. Loop authored.

## AutoLab log (cont.)
- 2026-07-04 B01: baseline=intermittent 429s on /markets under homepage load |
  benchmark=50 rapid GETs | result=0/50 429s after 3s TTL cache | IMPROVED.
- 2026-07-04 B07: baseline=~100 per-event Kalshi calls/cycle, constant 429s |
  benchmark=ingest-cycle 429 count in logs | result=0 in 3 min post-restart |
  IMPROVED. Board fetched in <=8 paginated calls + 1 series call.
- 2026-07-04 B04: news_scan_task added (hourly :35). Unit-verified: directional
  news -> unpriced -> news_arrival SignalEvent persisted (test passes with real
  event rows). *Live worker run interrupted by a Docker Desktop crash mid-
  verification (daemon died under parallel suite+build load); cron will run it
  hourly — verify citations appear in the next analyst brief.
- 2026-07-04 review: env_file made optional (fresh clones/CI would hard-fail).
- NOTE: full-suite run concurrent with 2 other suites + container build showed
  1 flaky failure (name lost to tail -1); clean rerun launched to pin it down —
  the two isolated runs both passed 1046/5.
- 2026-07-05 B08: baseline=full gate green on fresh clone (backend suite + ruff,
  frontend typecheck/lint/61 tests/build) | benchmark=user-journey smoke suite
  vs a live local stack (Postgres 16 + migrations 030 + uvicorn) | result=15/15
  green — 77-route GET sweep 0×5xx, signup→login→paper order→close→realized
  PnL, analyst brief + claim, assistant chat, agent-harness run risk-blocked
  with no order artifacts | outcome=IMPROVED. Deployed-demo fixes ship in this
  branch; user action needed: add LLM_PROVIDER/NIM_API_KEY/LLM_MODEL (+ EXA/
  FRED) as GitHub secrets, then run "Deploy Backend to HF Space" with
  sync_runtime_secrets=true.

- 2026-07-04 B04 LIVE-VERIFIED (post Docker recovery): full chain proven on
  real data. news_scan_task → 10 markets → news_arrival events carrying real
  Exa headlines (BBC/Opta/Yahoo). Analyst brief generator=llm (NIM qwen),
  reasons over + cites the actual story: Morocco brief names "a BBC headline
  explicitly questioning whether they are serious contenders" and cites
  "World Cup 2026: Unbeaten in 34 matches ... BBC Sport (up)". This is the
  "AI not analyzing well / not sourcing correctly" user complaint, closed.
  Follow-up quality fix folded in: headline threaded through
  news_lag_to_delta_event → detect → task → analyst citation + fallback brief.
