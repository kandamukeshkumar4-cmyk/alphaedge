# AlphaEdge Changelog

Paper-trading prediction market platform. Every entry cites a real git commit
SHA from this repository. Nothing here is invented.

Evidence command used while drafting:

```text
git log --oneline --merges -30
git log --oneline --all --grep="merge(loop"
```

---

## Wave 1 — Scoring pipeline & workstream platform

Core backend that turns market resolution into scored forecasts, plus the
loop-15 workstreams that made analytics, connectors, ML ops, and platform
ops production-ready.

| What shipped | Why it matters | SHA |
|---|---|---|
| V14 resolution → scoring pipeline (F01–F03) | Settled markets feed forecast scoring instead of dead-ending | `6c1a25d` |
| Loop 15-B analytics: leaderboard, attribution, watchlists, activity feed + WS, equity curve | Traders can see rank, who moved markets, and their paper P&L curve | `744a237` |
| Loop 15-C connectors: resilience, ESPN sports signals, source health, soak | Live sports and venue data keep flowing under load | `2b1b2e5` |
| Loop 15-D model registry, drift detect/API/alerts, flag-gated retrain | Model changes are tracked and drift is observable | `a3cb1b4` |
| Loop 15-E rate limiting, gated `/metrics`, ops alerts, OpenAPI snapshot, live soak | Platform stays safe and measurable under traffic | `bd2895a` |
| In-process loops: forecast_autolock, drift_detect, ops_alerts, portfolio_equity | Critical jobs run inside the API process instead of depending on external cron alone | `2d67d96` |

---

## Wave 2 — Freshness & forecast auto-lock

Home and market surfaces show real activity; auto-lock unblocks the
resolved-count path that accuracy gates depend on.

| What shipped | Why it matters | SHA |
|---|---|---|
| Freshness V1–V3: trending by recent activity, real signals rail, ticker freshness | Home feels live instead of static seed data | `89d1297` |
| V4 forecast auto-lock — resolved-count unblocker | Pre-close model forecasts can lock so scoring has real inputs | `941d209` |
| V5 closed-market hygiene | Closed markets no longer pollute open discovery UX | `5f8796a` |
| V7–V9 QA fixes: chart CSS-var crash, 375px overflow, accent contrast | Mobile and theme bugs that blocked trust in the UI are fixed | `b7fed4c` |

---

## Wave 3 — End-user QA, docs, load baseline

| What shipped | Why it matters | SHA |
|---|---|---|
| Loop 17 end-user QA journeys (Q1–Q4) — one-command Playwright suite | Critical user paths have an automated journey harness | `ef6ceb3` |
| Loop 18 QA hardening (Q5–Q8) — 23-test suite, mobile + auth + a11y | Regression coverage for mobile, auth, and accessibility | `5d91190` |
| Loop 19 documentation & launch readiness (W1–W5) | API/ops/user docs aligned for launch | `ee9d438` |
| Loop 20 load & performance baseline (L1–L4) | Performance has a measured baseline, not vibes | `4ee5662` |

---

## Wave 4 — Social, admin ops, notifications, frontend surfacing

| What shipped | Why it matters | SHA |
|---|---|---|
| Loop 22 social layer: profiles, follows, followed feed (migration 047) | Follow traders and read a followed activity feed | `405b3e6` |
| Loop 23 admin ops: market management + audit, user suspension, stats (migration 045) | Operators can manage markets and accounts safely | `75140ad` |
| Loop 24 notifications: model + API, producers, daily digest, WS channel | Alerts and digests reach users without polling alone | `29bdba2` |
| Loop 25 frontend surfacing: profiles, feed, bell, admin, eval — feature-complete | Wave-1/2 backends are visible in the product UI | `40c3e05` |
| Loop 25 mobile tap-target fix + lane-close docs | Mobile hit targets and lane closure recorded | `ea33676` |

---

## Wave 5 — Authz, CI, polish, multi-league sports, coverage

| What shipped | Why it matters | SHA |
|---|---|---|
| Loop 26 authz matrix + API journeys (Z1–Z4) | Permission boundaries are tested, not assumed | `3834a5f` |
| Loop 29 CI hardening: backend/frontend/e2e workflows + branch-protection doc | Merges are gated by real CI and documented branch rules | `455ebc8` |
| Loop 30 polish: display_name labels, attribution a11y, light-mode charts | Labels and charts work for all users and both themes | `e0df445` |
| Loop 31 multi-league sports signals (L1–L4) | Sports signals expand beyond a single league | `b923225` |
| Loop 32 coverage hardening: money/leakage/VOID/immutability tests (T1–T4) | Money paths and VOID/immutability are under test | `40ded0f` |

---

## Wave 6 — Pipeline input, papercuts, ops dashboard & retention

| What shipped | Why it matters | SHA |
|---|---|---|
| **Loop 33** catalog → `external_markets` bridge + funnel observability + honest resolved-count (B1–B3) | Autolock finally has input; the forecast pipeline is no longer starved at stage 0 | `64a74f7` |
| Loop 35 UX papercuts (U1–U3) | High-frequency UI annoyances removed | `349675e` |
| Loop 36 papercut backlog (Q1–Q3) | Second papercut pass closed | `7228cd9` |
| Loop 38 ops dashboard UI (O1–O4) | Loop health, source health, jobs, and admin stats on `/admin/observability` | `674e846` |
| Loop 39 data retention: FK-safe downsampling + prunes, dual-wired (R1–R3) | Historical tables can be pruned without FK disasters | `40ae11b` |

**Follow-on evidence (not a merge):** prod source flip documented when
`resolved_count` began reading real `forecast_scores` instead of the
paper-orders fallback — `f6bf87f` (`docs(loop40): THE FLIP`).

---

## Wave 7 — AI analyze fix, assistant depth, perf, visual regression

| What shipped | Why it matters | SHA |
|---|---|---|
| **Loop 41** AI Analyze: keyless path returns real deterministic analysis; menu only for unrecognized intents | “Analyze” no longer dumps a capability menu when no LLM key is set | `0d0f0e9` (completion; fix path `5cd46d3`, diagnosis `2871a97`) |
| **Loop 42** assistant intelligence depth M1–M4: on-demand model probability, bear-case, authenticated exposure | Chat can deepen analysis without inventing order flow | `2a50264` |
| Loop 42 keyless analyze signal-driver humanize + dedupe | Driver lines are readable and non-duplicative | `aa537f8` |
| Loop 43 perf round 2: market-detail + candles short-TTL caches (P1–P3) | Hot detail/candle reads are cheaper under load | `5bd60e3` |
| Loop 44 visual regression baselines (S1–S3) | UI regressions can fail CI with stable screenshots | `f7e7f64` |

---

## Wave 8 — Docs sync, Kalshi widening, locked-forecast transparency

| What shipped | Why it matters | SHA |
|---|---|---|
| **Loop 45** docs sync W1–W3 — `docs/api.md`, `docs/user-guide.md`, `docs/operations.md` aligned to the live surface | Docs match what the API and ops board actually expose | `298bf3f` |
| **Loop 46** Kalshi open-events widening: board-join miss audited, event-market fallback + caps, tests (K1–K3) | Kalshi events stop skipping 200/200 on empty board joins | `9b7af40` (impl `2fa7c7d`, audit `bea27a5`) |
| **Loop 48** unlock `GET /api/v1/markets/{slug}/locked-forecast` for F1/F2 | Backend exposes locked vs pre-lock model forecast honestly | `c64b04f` |
| **Loop 47** locked-forecast UI + resolved-count disclosure (F1–F3) | Market detail shows lock %, vs market delta, provisional flag; track-record shows source | `59bee3d` (F1–F2); F3 earlier `102ff42` |

---

## Wave 9 — Forecast lifecycle, cluster-gated A/B, Nemotron (flag-off)

Detailed narrative: [`docs/releases/wave-9.md`](docs/releases/wave-9.md).

| What shipped | Why it matters | SHA |
|---|---|---|
| **Loop 49** forecast lifecycle events E1–E4: WS `forecasts` channel, watcher notify on lock/resolve, bridge heartbeat parity | Clients and watchers learn about lock/score events in real time | `3e8f3a3` |
| **Loop 51** A/B harness retarget to `forecast_scores` — cluster gate (≥100), cluster bootstrap, MDE reporting; Dockerfile installs `ml-extra` so LightGBM is importable | Model A/B compares real scored forecasts, not paper-order proxies; LightGBM arm cannot silently fall back to XGBoost in image builds | `9e686ab` |
| **Loop 52** Nemotron-3 NIM reasoning signal + Ralph AutoLab lab (**flag-off**) | Optional NIM reasoning path and offline lab exist but stay disabled until explicitly enabled | `8e71c96` |

Supporting product proof for the V33 bridge (same tranche theme):

| Note | SHA |
|---|---|
| THE FLIP — prod `resolved_count` source = `forecast_scores` (7 scored) | `f6bf87f` |
| Accuracy-loop readiness runbook merge | `13b490e` |

---

## Wave 10 — Pods fleet, market context, heartbeat, provenance (2026-07-17)

Detailed narrative: [`docs/releases/wave-10.md`](docs/releases/wave-10.md).

Evidence basis while drafting Loop V66:

```text
git log --oneline --merges -15
```

| What shipped | Why it matters | SHA |
|---|---|---|
| **Loop 56** per-lock forecast provenance — migration `048_lock_provenance`, same-transaction provenance, honest nulls | A/B and operators can see *which path* wrote a lock; historic rows stay null (no invented backfill) | `ffedfa4` |
| Integrate `048_lock_provenance` head (unblocks multi-head ESCALATION) | Single Alembic head so later pod/whale/heartbeat migrations can chain | `133af64` |
| **Loop 58** master data pipeline — whale flow, venue gaps, market context API, graph wiring | Large-trade pressure, cross-venue gap, and `GET …/context` feed the desk and prediction graph (flag-gated graph features) | `4f9cb97` |
| Heartbeat migration renumber `051→052` onto `051_venue_gaps` (single head) | Keeps Alembic single-head after V58 venue-gap migration | `91239e3` |
| Loop 59 config union (V58 whale/gap + V59 heartbeat settings) | Land path for **heartbeat_manager** alongside whale/gap settings (no titled `merge(loop59)` in merge log) | `09af5eb` |
| **Loop 57** pods engine — three paper pods, scoring, `pod_runner` registration; re-chain `053_pods` onto `052_heartbeat` | Independent paper strategy pods with RiskService-only order path; public `GET /api/v1/pods` | `40aeeec` |
| **Loop 60** pods command center UI — fleet dashboard, decision terminal, context panels | Operators and users can open **`/pods`** for paper fleet telemetry without fake numbers | `8ae25a4` |
| **Loop 54** QA e2e specs — locked-forecast, bell/eval loading, resolved-count contract | Playwright contracts cover honesty surfaces that Wave 9/10 product claims depend on | `04162bc` |
| **Loop 61** continuous sentiment desk — adaptive cadence, trend features, analyst lenses (**flag-gated**) | News/sentiment becomes a continuous desk input for context/pods; ships behind flags (merge on integration line) | `ea2be72` |

Feature commits behind the merges (optional drill-down):

| Topic | SHAs |
|---|---|
| V56 tickets | `f58a1c1` P1 · `45e977a` P2 · `4dccbdb` P3 · `9ca6980` P4 |
| V58 tickets | `a1e5e96` D1 · `1d7f114` D2 · `b88de74` D3 · `bf119dd` D4 · `2f882dd` D5 |
| V59 tickets | `8c4c293` H1 · `75a3b54` H2 · `303180c` H3 · `15391a5` H4 · `ce099e9` H5 |
| V57 tickets | `f1ab750` P1 · `79497b5` P2 · `48933a3` P3 · `3003a8c` P4 · `539117c` P5 |
| V60 tickets | `bc14e33` U1 · `3c9f9dc` U2 · `313ee4d` U3 · `a9dc430` U4 · `ed9b223` U5 |
| V61 tickets | `7a9ac87` S1 · `45950a3` S2 · `aad10c9` S3 · `876ae23` S4 · `b28aa71` S5 |

**Prod observation (not a git SHA — live API check during V66 docs):**
`GET /api/v1/system/loops` on the uptime host showed `whale_flow`, `venue_gap`,
`heartbeat_manager`, and `pod_runner` with `running: true` / `status: ok`, and
`GET /api/v1/pods` returned three pods (`crypto_5m_momentum_fade`,
`longshot_fade`, `sports_value`) with `enabled: true` and
`paper_trading_only: true`. Code defaults for `PODS_ENABLED` /
`HEARTBEAT_MANAGER_ENABLED` remain false in-tree (`backend/app/core/config.py`);
operator env on Railway turns the runners on.

---

## How to verify a citation

```text
git show --stat <sha>
```

All SHAs in this file were checked to resolve in the local object database
while drafting Loop V50 (see `goals/loop-v50-changelog/STATE.md` verification
appendix).
