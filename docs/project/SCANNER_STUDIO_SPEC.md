# Scanner Studio — AI Market Scanner & Alert Builder (core module)

Source: user spec 2026-07-21 (from Xynth 24/7-scanning video), adapted to
AlphaEdge's paper-trading prediction-market domain. This supersedes the thin
"Automations" row in the Xynth feature inventory; Waves C tickets derive from
this document.

## What it is

User describes a monitoring setup in plain English → AI compiles it into a
structured, versioned scanner spec → builds an editable node-based workflow →
tests every step (visible progressive construction) → self-repairs recoverable
errors (validated before execution) → publishes → runs on a schedule → fires
rich dashboards + email/in-app alerts.

Three entry points: **Describe a scanner · Build visually · Start from a template**.

## Domain adaptation (stocks → prediction markets)

| Video concept | AlphaEdge equivalent |
|---|---|
| Options flow / premium aggregation | Whale flow / venue delta aggregation per market |
| Price trend + IV rank filter | Outcome-price trend + volatility-of-implied-prob filter |
| News sentiment classifier | Existing news_signal + sentiment_debate services |
| Bull call spread generation | Paper trade structure: side, size, entry prob, target, stop, payout multiple, max simulated loss — via deterministic backend math, never LLM arithmetic |
| Probability of profit / Greeks | Model prob vs market prob, time-to-lock decay, cluster exposure |
| "No broker orders" | ALWAYS: paper only; RiskService → OrderIntent → OrderBookService is the sole path and only on explicit user click |

## Pipeline (user spec, kept verbatim in structure)

Natural-language request → Alert Specification Compiler → schema/permissions
validator → workflow DAG compiler → preview + user approval → durable scheduler
→ market-data workers → Python analytics sandbox → LLM classification workers →
confluence + strategy engine → dashboard renderer → email/in-app notification.

## Alert specification (versioned JSON)

As per user spec: name, universe (market categories, min volume), schedule
(timezone, market-hours flag, interval), ordered typed steps
(WHALE_FLOW, PRICE_TREND, VOL_FILTER, NEWS_SENTIMENT, DIRECTION_ALIGNMENT,
PAPER_STRATEGY), delivery (email, in_app, cooldown_minutes). Version history +
rollback. Confluence supports strict equality OR weighted score
(flow 40 / trend 30 / news 20 / liquidity 10, min 80) — user-configurable.

## Node canvas requirements

Each node: status (waiting/running/completed/failed), input/output data,
summary, underlying code, charts/tables, duration, retry + edit controls.
Progressive build narration in sidebar ("Added whale-flow step", "Correcting
data type", "Testing notification", "Publishing alert").

## Self-healing (controlled)

Recoverable classes: data-type mismatch, missing column, provider schema
change, empty API response, rate limit, invalid market slug, expired/locked
market, temporary provider failure. AI proposes the repair; backend validates
replacement code (sandboxed, schema-checked) before execution. Non-recoverable
→ dead-letter + failure alert.

## Multi-model routing

Planner model (workflow compile) · code model (custom step logic) · classifier
model (structured bullish/bearish/neutral + confidence + rationale) ·
validation model (does workflow match the request). All market math is
deterministic backend code; LLMs never do arithmetic and never submit orders.

## Reliability requirements (launch gate)

Idempotent runs (no duplicate alerts) · per-market cooldown · market-calendar
awareness (game times / lock times) · stale-data rejection · source timestamp
on every result · max API + AI spend per run · max execution duration ·
retry policies by error category · dead-letter queue · repeated-failure alarm ·
version history + rollback · test mode on historical snapshots · NO automatic
order placement, ever.

## Durability decision

User spec suggests Temporal. Decision: **phase 1 uses ARQ + DB-checkpointed
run state** (run_history rows checkpoint per node; resume from last completed
node on worker restart) — Temporal is a heavy new infra dependency on Railway.
Revisit Temporal only if checkpointed-ARQ proves insufficient; record the
measurement, not vibes.

## Live status surface

Current run, last run, next run, duration, failed step, retry controls,
execution history, run-now, pause/resume, test-run + test-email before
publish, download results, creator attribution, public reusable templates,
fork + subscribe.

## Schedule fit

Extends Wave C (weeks 3-4 → 3-6): C-tickets now compile from this spec.
Wave A (terminal/steps/canvas) is the substrate — scanner nodes reuse the
step executor + React Flow canvas. Waves B/D unchanged.
