# Build Loop State — PolyScout backend

Spec: docs/project/BUILD_LOOP_BACKEND.md (read it before touching this file)
Baseline gate: full suite re-running (2026-07-02 Cursor); C3 tests 3/3 green.

## Queue

| id  | title                              | status | claimed_by | branch | last_update |
|-----|------------------------------------|--------|------------|--------|-------------|
| T01 | Kalshi WebSocket stream connector  | CLAIMED-OPUS | opus-4-8 | loop/T01-kalshi-ws | 2026-07-02 impl+tests done; awaiting IN-REVIEW |
| T02 | Polymarket CLOB WebSocket stream   | QUEUED | -          | -      | -           |
| T03 | Snapshot diff engine               | QUEUED | -          | -      | -           |
| T04 | Alignment scorer (trigger)         | QUEUED | -          | -      | -           |
| T05 | Whale tracker (data-api)           | QUEUED | -          | -      | -           |
| T06 | News→price lag detector            | QUEUED | -          | -      | -           |
| T07 | Analyst agent (briefs + claims)    | QUEUED | -          | -      | -           |
| T08 | Eval harness (claim grading)       | QUEUED | -          | -      | -           |
| T09 | Alert dispatch                     | QUEUED | -          | -      | -           |
| T10 | Scheduled research loop            | QUEUED | -          | -      | -           |
| T11 | LightGBM + SHAP (AutoLab)          | QUEUED | -          | -      | -           |
| T12 | Public briefs/track-record API     | QUEUED | -          | -      | -           |
| T13 | Instability/event-cat signal (worldmonitor-inspired; AGPL clean-room) | QUEUED (eligible after T03+T06) | - | - | added 2026-07-02 |
| T14 | Daily brief distribution (daily_stock_analysis-inspired; MIT) | QUEUED (eligible after T09+T10) | - | - | added 2026-07-02 |
| C1  | PaperOrder vs Order consolidation  | QUEUED | -          | -      | needs Opus sign-off before migration |
| C2  | PaperSignal → signal_events fold   | QUEUED | -          | -      | needs Opus sign-off before migration |
| C3  | Prometheus /metrics endpoint       | DONE   | cursor     | loop/chore-prometheus-metrics | 2026-07-02 Prometheus text format; stream+WS wired |
| C4  | WS fixture recording script        | DONE   | cursor     | loop/chore-ws-fixtures | 2026-07-02 record_ws_fixtures.py + format tests |
| C5  | Docs/notes upkeep                  | DONE   | cursor     | -      | 2026-07-02 explorer-notes PolyScout section |

## Decisions log

- 2026-07-02: Loop initialized by Fable 5 (planner). Ticket specs live in the spec doc §3; copy each into goals/build-loop/T{nn}.md on claim.
- 2026-07-02: Fable 5 (planner) added T13 + T14 to the queue (specs in spec doc §3). T13 = worldmonitor-inspired instability/event-category signal — AGPL-3.0 source: IDEAS ONLY, never clone/read its code; AutoLab-gated feature flag. T14 = daily_stock_analysis-inspired daily brief push — MIT: pattern/code adaptation OK with attribution; banned: its stock TA strategies, any agent-places-order pattern. Dependency rule: T13 claimable only after T03+T06 DONE; T14 only after T09+T10 DONE. Same maker/checker protocol: Opus builds, Cursor verifies (license compliance is an explicit review item for both tickets).
- 2026-07-02: Cursor Loop B iter 1 — C3 done. Replaced JSON stub `/metrics` with `prometheus-client` counters; `record_brief_generated` / `record_claim_scored` hooks for T07/T08.

## Blockers

(none)

## Metrics

- Backend tests baseline: 434 passed, 4 skipped (2026-06-12) + 3 prometheus tests (2026-07-02)
- Stream latency (exchange→hub): not yet measured
- Analyst brief latency: not yet measured
- Walk-forward Brier/CLV baseline (for T11 AutoLab): not yet measured

## Loop B log

- 2026-07-02 Cursor iter 1: no IN-REVIEW; claimed C3; gate green (C3 tests + ruff); T01 still CLAIMED-OPUS.
- 2026-07-02 Cursor iter 2 (heartbeat): no IN-REVIEW; claimed C4; `scripts/record_ws_fixtures.py` + 4 format tests green; T01 still CLAIMED-OPUS.
- 2026-07-02 Cursor iter 3 (heartbeat): no IN-REVIEW; C5 explorer-notes updated; stream subset 35 passed; T01 looks ready for Opus to flip IN-REVIEW.
- 2026-07-02 Cursor iter 4 (heartbeat): idle — no IN-REVIEW; C1/C2 blocked on Opus sign-off; C3–C5 done; waiting on Opus for T01 handoff.
- 2026-07-02 Cursor iter 5 (heartbeat): still idle; T01 unchanged CLAIMED-OPUS; base stream tests green.
- 2026-07-02 Cursor iter 6 (heartbeat): no state change; Loop B blocked on Opus T01 handoff.
