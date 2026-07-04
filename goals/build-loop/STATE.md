# Build Loop State — PolyScout backend

Spec: docs/project/BUILD_LOOP_BACKEND.md (read it before touching this file)

---

# Loop C — Unified Intelligence (ACTIVE, initialized 2026-07-03)

Spec: docs/project/BUILD_LOOP_UNIFIED.md (READ IT FIRST — guardrails §G, license
policy G4 from verified GitHub API data, stop conditions §5). Baseline gate at
init: backend 669p/5s ruff clean (2026-07-02); frontend lint/typecheck/build green.

## Loop C Queue

| id  | title                                   | status | claimed_by | deps | last_update |
|-----|-----------------------------------------|--------|------------|------|-------------|
| U01 | Unified market search (PM+Kalshi)       | DONE   | -          | -    | 2026-07-03 verifier PASS (701p/5s, §G clean, UI reachable) |
| U02 | Unified activity feed                   | DONE   | -          | -    | 2026-07-03 iter 2 PASS (732p/5s, §G clean, feed page + nav reachable) |
| U03 | Decision dashboard (Bet/Pass card)      | DONE   | -          | U01  | 2026-07-03 iter 3 verifier PASS (749p/5s, §G clean, both deviations OK) |
| U04 | Portfolio exposure analysis             | DONE   | -          | -    | 2026-07-03 iter 4 PASS (774p/5s inline verify, §G clean, 40% boundary OK); committed b0ff6c0 |
| U05 | Assistant chat (analysis-only, no-order)| DONE   | -          | U04  | 2026-07-03 iter 5 PASS (795p/5s inline verify, §G2 safety-critical clean); committed 0caf20c |
| U06 | Agent Builder "Clone-lite"              | DONE   | -          | -    | 2026-07-03 iter 6 verifier PASS (821p/5s, G3 3-layer, single head 029); committed 6a60df6 |
| U07 | Clone leaderboard / arena               | DONE   | -          | U06  | 2026-07-03 iter 7 verifier PASS (845p/5s, scorer reuse, honest stub); committed dc43429 |
| U08 | Multi-model ensemble + router (AutoLab) | IN-REVIEW | opus-4-8 maker → verifier | - | 2026-07-03 iter 8: maker done 886p/5s, honest iter=0 flag OFF, verifier running |
| U09 | Memory / learning loop (AutoLab)        | TODO   | -          | -    | 2026-07-03 queued |
| U10 | Backtest replay + realistic fills       | TODO   | -          | -    | 2026-07-03 queued |
| U11 | Cross-platform arb hardening            | TODO   | -          | U02  | 2026-07-03 queued |
| U12 | Observability + calibration drift       | TODO   | -          | -    | 2026-07-03 queued |
| U13 | Personalization (AI learns the user)    | TODO   | -          | U04,U05 | 2026-07-03 queued (owner request) |

## Loop C Decisions log

- 2026-07-03 iter 7 VERDICT: U07 **PASS** → DONE, committed dc43429. Verifier
  confirmed all 6 integrity checks: (1) scorer genuinely reuses T08 score_claim +
  aggregate_claims (service:41-42,229), Brier/accuracy from overall.*, no
  divergent formula; (2) no fabricated metrics, honest empty (n_graded=0,
  brier=None); (3) PROVISIONAL_MIN=30 imported from analyst_metrics, consistent;
  (4) /leaderboard + /{id}/scorecard registered before /{clone_id} catch-all
  (clones.py:142,234,286); (5) live-vs-stubbed statement accurate — claims derived
  compute-time from predicted_prob vs OddsSnapshot via real scorer, no BriefClaim
  persistence (future ticket); (6) no order-path imports. Minor notes (non-blocking):
  scorer-import test is text-scan not AST; no HTTP integration test on /leaderboard
  (route order verified by declaration). Full gate 845p/5s, single head 029.
  New baseline: **845p/5s**. Clones pillar (U06 build + U07 arena) COMPLETE.
  Iteration 8: U08 (multi-model ensemble + router — AutoLab-gated) claimed.

- 2026-07-03 iter 6 VERDICT: U06 **PASS** → DONE, committed 6a60df6. Verifier agent
  (recovered — no 529/limit this round) confirmed all 6 G3 checks: (1)
  VETTED_NODE_NAMES = frozenset(name for name,_ in GRAPH_NODES) derived not copied
  (clone_service.py:32); (2) unknown node rejected at Pydantic 422 + service
  UnknownNodeError + runtime guard _run_clone_graph:258; (3) zero order-path
  imports, AST tests genuinely parse+walk; (4) params clamped edge[0,0.50]
  cooldown[60,10080]; (5) versioning retains old (is_latest=False, not
  overwritten); (6) UI fetches vetted nodes from GET /api/v1/clones/nodes.
  paper_trading_only hardcoded True not user-settable. Full gate 821p/5s, ruff
  clean, single alembic head 029, frontend green. New baseline: **821p/5s**.
  Iteration 7: U07 (clone leaderboard/arena, dep U06 satisfied) claimed.

- 2026-07-03 iter 5 VERDICT: U05 **PASS** → DONE, committed 0caf20c. Verifier agent
  cut off by session limit (10pm reset) → orchestrator verified INLINE (this is the
  safety-critical ticket, done carefully). §G2 CONFIRMED: assistant.py zero
  order-path import lines (grep of import statements), ASSISTANT_ALLOWED_TOOLS =
  {get_odds,get_features,get_exposure,get_briefs,get_agent_trace} — no
  submit_order_intent; AST guardrail test genuinely ast.parse+walk ImportFrom (not
  assert True), 5 guardrail tests pass. Full gate: 795p/5s, ruff clean, frontend
  lint/typecheck/build green. UI: AnalystChatDrawer mounted market-detail:225 +
  portfolio:176, analysis-only banner unconditional static div (testid line 264),
  zero order controls in drawer. New baseline: **795p/5s**. U04+U05 both DONE →
  U13 (personalization) now UNBLOCKED. Iteration 6: U06 (Agent Builder Clone-lite)
  claimed per build order (U06→U07, then U08-U12, U13).

- 2026-07-03 iter 4 VERDICT: U04 **PASS** → DONE, committed b0ff6c0 (first clean
  atomic per-ticket commit). Verifier agent hit transient 529 (0 tool uses) →
  orchestrator verified INLINE: full backend gate 774p/5s exit 0, ruff clean,
  frontend lint/typecheck/build green. §G clean: exposure_service.py + portfolio.py
  no OrderBookService/RiskService imports (docstring guardrail note only),
  read-only aggregation, PAPER_TRADING_ONLY untouched, EXPOSURE_DISCLAIMER in
  response. CRITICAL BOUNDARY confirmed: exposure_service.py:199 `concentrated=
  pct > 40.0` (strict) matches test_concentration_exactly_at_threshold_not_
  concentrated — exactly 40% is NOT concentrated. 25 tests genuine (underlier
  derivation across NBA/FIFA/crypto/elections + aggregation + boundary + empty).
  UI mounted portfolio/page.tsx:171. New baseline: **774p/5s**. Iteration 5: U05
  (analysis-only assistant chat, dep U04 satisfied) claimed. NOTE: U04+U05 both
  DONE will unblock U13 (personalization).

- 2026-07-03 iter 3 VERDICT: U03 **PASS** → DONE. Verifier independent gate:
  749 passed, 5 skipped (baseline 732), ruff clean, frontend all green. §G clean:
  agent_trace.py no order-path imports (docstring mention only), paper_trading_only
  =True hardcoded in response, DecisionCard advises-only (no execution control),
  config validator untouched. derive_verdict boundaries genuinely tested (14 tests,
  edge at exactly 0.019/0.02/0.05 + provisional-forces-non-BET). UI reachable:
  DecisionCard mounted market-detail-client.tsx:223, AIAnalyzeButton opens it.
  Deviations RULED ACCEPTABLE: (a) AITakePanel orphaned = inert dead code, cleanup
  later; (b) CalibrationSparkline approximate curve but honest empty state + real
  Brier number, not misleading — future U12 can wire binned reliability data.
  COMMIT NOTE: U03 files already committed (aa6fd0a WIP snapshot + parallel
  e2e-loop `git add -A` commits swept final refinements — shared-branch
  interleaving). Work is safe + verified green; history is just non-atomic.
  New baseline: **749p/5s**. Iteration 4: U04 (portfolio exposure) claimed.

- 2026-07-03 iter 2 VERDICT: U02 **PASS** → DONE. Maker #2 completed the build
  before being killed mid-self-verification; orchestrator finished verification
  inline (no separate verifier agent — avoided re-doing finished work on limited
  quota). Artifacts: api/v1/feed.py (300 lines) + api/v1/activity.py, test_feed_api
  + test_activity_api (21 scoped tests green), frontend /feed/page.tsx, "Feed" nav
  entry (QuestHeader.tsx:49), feed_router registered in main.py:35. FULL GATE:
  backend pytest exit 0, 737 collected → 732 passed, 5 skipped (baseline 701);
  ruff clean; frontend typecheck+lint+build all green. §G sweep CLEAN: no
  OrderBookService/RiskService imports in feed/activity, no live HTTP in feed path
  (DB-read only), PAPER_TRADING_ONLY validator untouched (config.py:164, default
  True). New test baseline: **732p/5s**. Iteration 3: U03 (Bet/Pass decision
  dashboard, dep U01 satisfied) claimed, maker launched.

- 2026-07-03 INCIDENT + RECOVERY: U02 maker #1 killed mid-build by session usage
  limit; simultaneously the working tree was git-stashed (all tracked mods →
  stash@{0}), leaving untracked new files orphaned (U01 tests red on import).
  Recovery: owner authorized `git stash pop` — clean, 0 conflicts, 52 files
  restored; U01 re-verified 19/19 green. U02 maker #2 launched, instructed to
  audit + finish the partial api/v1/feed.py left by maker #1. LESSON (open
  recommendation to owner): commit a checkpoint after each verified ticket so a
  stray stash/reset can't sweep loop output again.

- 2026-07-03: Fable 5 (planner) — U13 "Personalization (AI learns the user)"
  added to queue on owner request (Questflow capability #4). Spec in
  BUILD_LOOP_UNIFIED.md §4, UI contract in BUILD_LOOP_UNIFIED_UI.md. Deterministic
  profile from paper history only, LLM narrates, deps U04+U05. Queue now 13
  tickets; stop conditions unchanged (40-iter cap still applies to the total).

- 2026-07-03 iter 1 VERDICT: U01 verifier **PASS** → DONE. Independent gate rerun:
  pytest 701p/5s, ruff clean, frontend lint/typecheck/build green. §G sweep clean:
  G1 validator untouched (config.py:166), G2 no order-path imports in new modules,
  search path DB-only (no live connector calls), G4 ATTRIBUTIONS.md pmxt entry
  verified adapted-not-pasted. Ranking spec confirmed (title-match → status →
  volume, market_service.py:407-413). UI reachable: cmd-k global + header click,
  modal mounted in QuestHeader.tsx:120, platform badges + live YES price render.
  Deviation (new SearchCommandModal.tsx vs extending MarketSearch.tsx) accepted —
  additive, /markets search preserved. New test baseline: **701p/5s**.
  Iteration 2: U02 (unified activity feed) claimed, maker launched.

- 2026-07-03 iter 1: U01 maker (implementer agent) DONE → IN-REVIEW. Added backend
  unified search (schemas/market.py UnifiedMarketSearchResult pmxt-attributed;
  market_service.search_markets + rank helpers; GET /api/v1/search; 19 tests) +
  frontend SearchCommandModal.tsx (cmd-k palette, grouped cross-platform results,
  badges, empty-state trending) wired into QuestHeader. Maker gate: 701p/5s, ruff
  clean, frontend lint/typecheck/build green. docs/ATTRIBUTIONS.md created (pmxt
  MIT). Deviation: NEW SearchCommandModal.tsx instead of extending MarketSearch.tsx
  (existing /markets search preserved) — verifier to judge. Verifier agent launched
  (adversarial: reruns full gate + §G sweep + UI-reachability). Awaiting verdict.

- 2026-07-03: Fable 5 (planner) — Loop C armed for execution. (1) All 16 candidate
  repos re-verified via git ls-remote and shallow-cloned into vendor-study/
  (git-ignored, §G4 personal-project mode) — includes the 5 beyond the report's
  catalogue: CloddsBot, pmxt, Polymarket/agents, Jon-Becker, spfunctions list.
  (2) UI-FIRST rule added: docs/project/BUILD_LOOP_UNIFIED_UI.md now defines the
  user-visible contract per ticket; a U-ticket is NOT DONE unless its surface is
  reachable in the frontend (checker item). Global nav target:
  Feed | Markets | Signals | Clones | Leaderboard | Portfolio | Research.
  (3) Build order per UI plan: U01→U02→U03 first (visible parity shell), then
  U04/U05, then U06/U07, then U08–U12. (4) Prior session shipped AIAnalyzeButton
  (on-card modal → AITakePanel); U03's DecisionCard absorbs it.

- 2026-07-03: Loop C initialized by Opus 4.8. Sources: Questflow thread (2026-07-02)
  + user's technical report docx. TRUTH-FIRST corrections encoded in spec §0: the
  report's #1 gap (real-time streaming) was ALREADY BUILT in Loop A/B (T01–T04) —
  no streaming rebuild tickets. All 14 candidate repos verified to exist via GitHub
  API; license split encoded in §G4 (homerun AGPL + all no-license arb repos =
  IDEAS ONLY clean-room; pmxt/TradingAgents/CloddsBot/Polymarket-agents/Jon-Becker/
  MCP servers = MIT/Apache, minimal-pattern adaptation with attribution; all
  live-execution code banned regardless of license). Stop conditions: queue empty,
  40-iteration hard cap, 2 no-measure planner passes, or guardrail conflict ×3.
  PAPER_TRADING_ONLY and the RiskService order path are untouchable (§G1–G3).
- 2026-07-03: Owner decision — G4 relaxed to PERSONAL-PROJECT MODE. Cloning/reading
  ALL repos allowed (vendor-study/, git-ignored). MIT/Apache: copy freely w/
  attribution. AGPL (homerun): adapt allowed, accepted consequence = AGPL
  obligations if derived code ships; mark derived files. No-license repos: prefer
  reimplement over paste (infringement + interview-defensibility), provenance
  headers if pasted. UNCHANGED: execution/live-trading code banned from every
  source; guardrails §G1–G3 intact. Checker item is now "provenance documented +
  no execution code".

---

## ✅ BUILD LOOP COMPLETE (2026-07-02)
All 14 T-tickets DONE (Cursor-verified). Chores C3–C5 DONE; C1–C2 DEFERRED (Opus
sign-off — risky refactor of guardrail-critical order path, no product benefit).
Final gate: **669 passed, 5 skipped, ruff clean, single alembic head 027**.
§6 final review: PASS — guardrails intact (PAPER_TRADING_ONLY enforced; new PolyScout
code never touches RiskService→OrderIntent→OrderBookService; no keys; clean-room/MIT
license compliance verified). UI is OUT OF SCOPE (separate BUILD_LOOP_UI.md consumes
the T12 API contract). Baseline was 434 tests (pre-loop) → 669 (+235 across the loop).

## Queue

| id  | title                              | status | claimed_by | branch | last_update |
|-----|------------------------------------|--------|------------|--------|-------------|
| T01 | Kalshi WebSocket stream connector  | DONE   | -          | (shared tree) | 2026-07-02 Cursor re-review PASS |
| T02 | Polymarket CLOB WebSocket stream   | DONE   | -          | (shared tree) | 2026-07-02 Cursor verify PASS; migration 023 |
| T03 | Snapshot diff engine               | DONE   | -          | (shared tree) | 2026-07-02 Cursor verify PASS |
| T04 | Alignment scorer (trigger)         | DONE   | -          | (shared tree) | 2026-07-02 Cursor verify PASS |
| T05 | Whale tracker (data-api)           | DONE   | -          | (shared tree) | 2026-07-02 Cursor verify PASS (onchain kept — deviation) |
| T06 | News→price lag detector            | DONE   | -          | (shared tree) | 2026-07-02 Cursor verify PASS; T13 now eligible |
| T07 | Analyst agent (briefs + claims)    | DONE   | -          | (shared tree) | 2026-07-02 Cursor verify PASS |
| T08 | Eval harness (claim grading)       | DONE   | -          | (shared tree) | 2026-07-02 Cursor verify PASS |
| T09 | Alert dispatch                     | DONE   | -          | (shared tree) | 2026-07-02 Cursor re-verify PASS (gate blocker fixed) |
| T10 | Scheduled research loop            | DONE   | -          | (shared tree) | 2026-07-02 Cursor re-verify PASS |
| T11 | LightGBM + SHAP (AutoLab)          | DONE   | -          | (shared tree) | 2026-07-02 Cursor verify PASS; honest AutoLab (iterations=0) |
| T12 | Public briefs/track-record API     | DONE   | -          | (shared tree) | 2026-07-02 Cursor verify PASS; UI-loop contract |
| T13 | Instability/event-cat signal (worldmonitor-inspired; AGPL clean-room) | DONE   | -          | (shared tree) | 2026-07-02 Cursor re-verify PASS (iter 21) |
| T14 | Daily brief distribution (daily_stock_analysis-inspired; MIT) | DONE   | -          | (shared tree) | 2026-07-02 Cursor re-verify PASS (iter 21) |
| C1  | PaperOrder vs Order consolidation  | DEFERRED | opus-4-8 (sign-off) | - | 2026-07-02 Opus sign-off: DO NOT execute — 42 active refs, guardrail-critical order path, no benefit |
| C2  | PaperSignal → signal_events fold   | DEFERRED | opus-4-8 (sign-off) | - | 2026-07-02 Opus sign-off: DO NOT execute — 28 active refs, tested, no benefit; risk > reward |
| C3  | Prometheus /metrics endpoint       | DONE   | cursor     | loop/chore-prometheus-metrics | 2026-07-02 Prometheus text format; stream+WS wired |
| C4  | WS fixture recording script        | DONE   | cursor     | loop/chore-ws-fixtures | 2026-07-02 record_ws_fixtures.py + format tests |
| C5  | Docs/notes upkeep                  | DONE   | cursor     | -      | 2026-07-02 explorer-notes PolyScout section |

## Decisions log

- 2026-07-02: Loop initialized by Fable 5 (planner). Ticket specs live in the spec doc §3; copy each into goals/build-loop/T{nn}.md on claim.
- 2026-07-02: Fable 5 (planner) added T13 + T14 to the queue (specs in spec doc §3). T13 = worldmonitor-inspired instability/event-category signal — AGPL-3.0 source: IDEAS ONLY, never clone/read its code; AutoLab-gated feature flag. T14 = daily_stock_analysis-inspired daily brief push — MIT: pattern/code adaptation OK with attribution; banned: its stock TA strategies, any agent-places-order pattern. Dependency rule: T13 claimable only after T03+T06 DONE; T14 only after T09+T10 DONE. Same maker/checker protocol: Opus builds, Cursor verifies (license compliance is an explicit review item for both tickets).
- 2026-07-02: Cursor Loop B iter 1 — C3 done. Replaced JSON stub `/metrics` with `prometheus-client` counters; `record_brief_generated` / `record_claim_scored` hooks for T07/T08.
- 2026-07-02: Opus — **§6 FINAL REVIEW PASS + C1/C2 SIGN-OFF (loop complete).** All 14 T-tickets DONE (Cursor-verified through the adversarial maker/checker loop, incl. two correct FAIL→rebuild cycles on T13/T14). C1/C2 SIGN-OFF = DEFER: investigated usage — PaperOrder 42 active refs (orders API/calibration/position service/schemas), PaperSignal 28 active refs (signal service/routes); both are tested, guardrail-critical order-path models, NOT dead code. Consolidating them is a large risky refactor with zero PolyScout benefit → deferred (principal-eng call: don't destabilize a green complete backend for a cosmetic dedup). §6 guardrail sweep PASS: PAPER_TRADING_ONLY enforced by validator; grep confirms no new signals/agents/eval/services module imports OrderBookService/RiskService (order path untouched); no hardcoded keys in new modules; only worldmonitor mentions are clean-room attribution docstrings (no AGPL code). Final gate 669p/5s, ruff clean, migration chain clean 022→027 (single head). Delivered: streams→diff→alignment trigger→whale/news layers→AI analyst (cited briefs + falsifiable claims)→no-lookahead eval harness + public track record→alerts→daily research desk→LightGBM/SHAP infra→public API→instability signal→daily distribution. UI OUT OF SCOPE.
- 2026-07-02: Opus — T13 + T14 SPEC-COMPLETION after Cursor FAILs (both were under-built vs the richer spec — Cursor's checks were correct). T13: added event_taxonomy.py (15 cats), reworked instability.py to per-region rolling-decay 0-100 + threshold-cross → INSTABILITY_SHIFT DeltaEvent → alignment (NEWS layer), forecasting features flag-gated (Politics/Geopolitics/Economics only, NBA never), honest AutoLab (stalled, no election dataset). T14: added services/daily_brief.py (per-market assembly: price/model/edge/CLV-gate/news/whale + claim scoreboard) + daily_brief_markdown/compact(≤4000), distribution metadata on digest row. Both gate green 669p/5s, ruff clean. Both re-flipped IN-REVIEW for Cursor re-verify. ALL 14 T-TICKETS now built. Remaining: Cursor verify T13/T14, chores C1/C2 (need Opus sign-off), final review pass §6.
- 2026-07-02: Opus — T13 (instability/event-category signal) → IN-REVIEW (v1, later FAILed + rebuilt). CLEAN-ROOM from concept only (worldmonitor is AGPL — no source read/copied; taxonomy/patterns/formula all original). signals/instability.py: EVENT_CATEGORIES + categorize_event + instability_score (composite 0-1, monotonic, clamped) + InstabilityService (flag-gated persistence to signal_events, headline_eligible=False). Guardrail 3 structurally enforced: instability is NOT a DeltaKind / not in delta_to_layer_vote, so it can never become an alignment layer / trade trigger — feature/context only. Flag OFF by default. Gate 641p/5s, ruff clean, no schema change. LICENSE COMPLIANCE flagged as Cursor's explicit review item. Claiming T14 (daily brief distribution — MIT, code adaptation OK with attribution). NOTE: T12 confirmed DONE by Cursor. Remaining: T14, chores C1/C2, final review pass §6.
- 2026-07-02: Opus — T12 (public API, the UI-loop contract) → IN-REVIEW. api/v1/briefs.py: GET /briefs (paginated + market/category/kind filters, eager-loaded claim), /briefs/{id}, /analyst/track-record (T08 aggregates incl per-version), /analyst/track-record/claims (graded claims transparency), /markets/{slug}/latency (freshness badge). schemas/analyst_api.py response models; registered in main.py. Fixed async lazy-load (selectinload) + corrected a wrong rate-limit-header assumption (SlowAPI middleware enforces globally but emits headers only with a route decorator). Gate 625p/5s, ruff clean, no DB schema change. Claiming T13 (worldmonitor-inspired instability signal — AGPL: IDEAS ONLY, clean-room, never read its source). NOTE: T09/T10/T11 confirmed DONE by Cursor. T14 also eligible now (T09+T10 DONE). Remaining: T13, T14, chores C1/C2, final review pass §6.
- 2026-07-02: Opus — T11 (LightGBM+SHAP, AutoLab ticket) → IN-REVIEW. model_registry (lightgbm optional → xgboost fallback), ml/explain.py (SHAP-or-importance-fallback top-5 features), ForecastPrediction.top_features (best-effort), PredictionLog.explanation + migration 027, ml-extra optional dep group. TRUTH-FIRST: lightgbm+shap NOT installable in this env, so the LightGBM-vs-XGBoost A/B cannot run — I built the infra and recorded an HONEST AutoLab line (iterations=0, no fabricated improvement, default stays XGBoost so baseline preserved). ALSO FIXED the dead XGBClassifier import in trainer.py that had reddened the shared ruff gate and FAILed T09+T10 verify — gate now green (615p/5s), so T09+T10 flipped back to IN-REVIEW for re-verify. Claiming T12 (public API — the UI-loop contract). Remaining: T12, T13, T14, chores C1/C2.
- 2026-07-02: Opus — T10 (scheduled research loop) → IN-REVIEW. ResearchDigestService: pure rank_markets (24h movement × open-interest), select_top_markets, assemble_digest (today's briefs/claim-record/unpriced-news/whale-moves), run_daily (idempotent-per-UTC-day → analyst per market cooldown-respected → digest AnalystBrief kind=digest). morning_research_task daily 06:00. Gate 604p/5s, ruff clean, no schema change. Claiming T11 (LightGBM+SHAP — AutoLab ticket). NOTE: T14 now unblockable once T09+T10 both DONE by Cursor. T13 also eligible (T03+T06 DONE). Remaining after T11: T12 (public API), T13, T14, chores C1/C2.
- 2026-07-02: Opus — T09 (alert dispatch) → IN-REVIEW. AlertDispatchService fans alignment + brief events to alerts table + WS hub 'alerts' + optional Telegram/webhook (OFF by default, injectable transport, ≤400 chars), process-level dedupe with safety cap. Wired into persist_alignment + analyst persist_publish (try/except-isolated). Key test: disabled flags → zero external calls (mock transport). Gate 597p/5s, ruff clean, no schema change. Claiming T10 (scheduled research loop). NOTE: T08 confirmed DONE by Cursor (hire-signal bar met). T14 needs T09+T10 DONE; T13 eligible now (T03+T06 DONE).
- 2026-07-02: Opus — T08 (eval harness, THE HIRE-SIGNAL) → IN-REVIEW. claim_scorer (pure score_claim 4 directions × correct/incorrect/void; ClaimScorerService with STRICT no-lookahead — p_h only from (created_at, horizon], negative-control test proves post-horizon rows ignored), analyst_metrics (accuracy+Brier by category/claim-type/model/prompt × 7/30/all windows, provisional<30), citation_audit (structural post-hoc detection, no LLM), AnalystEvalAggregate + migration 026, score_claims_task (15min) + analyst_aggregates_task (hourly). Fixed a load-bearing tz-naive/aware datetime bug (_as_utc). void when insufficient data — never guessed. Gate 591p/5s, ruff clean, single head 026. Claiming T09 (alert dispatch). NOTE: T07 confirmed DONE by Cursor. T13 eligible (T03+T06 DONE); T14 needs T09+T10.
- 2026-07-02: Opus — T07 (analyst agent, THE FLAGSHIP) → IN-REVIEW. LangGraph-optional async pipeline: gather market state + evidence (news/whale signal_events + model via predict_market) → write_brief (LLM or deterministic fallback, runs with NO key) → deterministic machine-checkable claim → persist_publish (AnalystBrief+BriefClaim, hub 'briefs', record_brief_generated). schemas/brief.py (≥1 citation enforced), migration 025 (analyst_briefs+brief_claims, chains 024). Wired in-process from persist_alignment (cooldown-gated, try/except-isolated). CLAIM is deterministic (never LLM text) so T08 can grade it. Gate 567p/5s, ruff clean, single head 025. Claiming T08 (eval harness — the hire-signal; spec says DO NOT cut corners). NOTE: T05+T06 confirmed DONE by Cursor (onchain deviation accepted).
- 2026-07-02: Opus — T06 (news→price lag detector) → IN-REVIEW. Pure `evaluate_news_lag` (stale/low-relevance/neutral/priced-in/unpriced boundaries), `NewsLagService.detect` reads odds_snapshots price-at-news vs price-now, emits news_arrival(unpriced) DeltaEvent → diff persist + T04 scorer. Sentiment is metadata + directional vote only (guardrail 3) — lone news layer can't fire the analyst. Design choice flagged for Cursor: missing price history → treated as unpriced (safe under ≥3-layer gate; one-branch to flip if stricter preferred). Gate 555p/5s, ruff clean, no schema change. All 3 alignment layers (price/whale/news) now feed T04. Claiming T07 (analyst agent — the flagship). NOTE: T06 DONE (once Cursor verifies) makes T13 eligible (T03+T06).
- 2026-07-02: Opus — T05 (whale tracker) → IN-REVIEW. NEW polymarket_data_api.py connector (leaderboard/positions/trades + defensive normalizers), whale qualification in smart_money.py (≥50 resolved / ≥65% acc / ≥1.5 PF / one-hit-wonder guard), position diff→whale_delta, WhaleTrackerService.snapshot_and_diff feeding the T04 scorer, WalletPositionSnapshot table + migration 024, two ARQ tasks. DEVIATION (truth-first, flagged for Cursor): spec said "delete onchain.py (it is a stub)" — it is NOT a stub (working tested subgraph connector used by wallet_service + 2 tests), so I KEPT it and added data-api as the whale source instead. FOLLOW-UP: live data-api endpoint paths/fields best-effort — verify against live API before trusting whale signals (fails safe: missing fields → no qualification). Gate 545p/5s, ruff clean, single head 024. Claiming T06 (news→price lag). Reminder: T06 DONE unblocks T13.
- 2026-07-02: Opus — T04 (alignment scorer / analyst trigger) → IN-REVIEW. Per-market rolling-window scorer counting DISTINCT layers per direction (price/whale/news + optional model 4th layer via injected vote), fusion weights (no self-learning), dedupe with episode-reset, `persist_alignment` → signal_events type=alignment + DomainEvent `analyst.trigger`. Wired into runner after the diff engine. Break pass caught + fixed a dedupe hole (partial window expiry never reset dedupe while price kept ticking). Gate 525p/5s, ruff clean, no schema change. Claiming T05 (whale tracker). Reminder: TrackedWallet model already exists in models.py (T05 groundwork); T05 migration must chain from head 023.
- 2026-07-02: Opus — T03 (snapshot diff engine) → IN-REVIEW. Pure `compute_market_delta` (price_jump/orderbook_flip/volume_surge, strict boundaries + `_EPS` float-noise guard), `DiffEngineService` with in-memory state (Redis backend optional behind `diff_state_backend`), `persist_deltas` → signal_events + DomainEventBus, wired into runner tick path (price ticks only — orderbook_flip stays pure-tested until a real aggregate-size source; break pass caught that Polymarket book gives prices not sizes). Gate 513p/5s, ruff clean, no schema change. Claiming T04 (alignment scorer). NOTE: T13 becomes eligible once T03 is DONE + T06 DONE.
- 2026-07-02: Opus — addressed all 3 Cursor T01 findings + completed T02 in one pass (they share main.py/runner.py). T01 fixes: (1) latency accept test `test_exchange_to_publish_latency_under_50ms`; (2) degrade-to-polling proven via pure `background_loop_plan(settings)` + test_stream_loop_plan.py; (3) stream tasks now restart-guarded (while-True + 30s backoff) instead of dying on raise. T02: Polymarket CLOB WS parser/stream + Market.clob_token_id column + migration 023 + ingest token-id persistence. Gate: 498 passed, 5 skipped, ruff clean, single alembic head (023). Both T01 + T02 → IN-REVIEW. NOTE FOR CURSOR: T02 schema change (nullable Market.clob_token_id + migration 023) is an explicit review item; alembic head is single (chains 022→023), T05 should chain from 023. Claiming T03 (diff engine) next.
- 2026-07-02: Opus — T01 → IN-REVIEW. Full gate GREEN (477 passed, 5 skipped, ruff clean) with T01 code. Fixed a stray unused-import lint in tests/test_kalshi_live_ingest.py (from parallel work) to keep the shared tree gate-clean. COORDINATION NOTE: Opus + Cursor share ONE working tree (no worktree isolation), so branch-per-ticket from the spec is not literally applied; handoff is via this STATE.md and Cursor re-running the gate. Opus is NOT committing (would sweep up Cursor's in-flight chore edits). T01 review scope for Cursor: streams/base.py, streams/kalshi_ws.py, streams/runner.py, price_feed_worker.persist_and_publish_tick refactor, main.py _kalshi_stream_loop wiring, config flags. Full break-pass findings in goals/build-loop/T01.md. Claiming T02.

## Blockers

(none)

## Metrics

- Backend tests baseline: **477 passed, 5 skipped** (2026-07-02 Cursor gate)
- After T01: 477 passed, 5 skipped, ruff clean (2026-07-02) — +43 tests incl. Kalshi WS parser + reconnect + persist helper
- After T01-fixes + T02: **498 passed, 5 skipped**, ruff clean, single alembic head 023 (2026-07-02) — +21 tests: Polymarket parser, degrade plan, latency accept, token-id persistence
- After T03: **513 passed, 5 skipped**, ruff clean (2026-07-02) — +15 tests: diff engine boundaries, service seed/idempotent/merge, delta persistence
- After T04: **525 passed, 5 skipped**, ruff clean (2026-07-02) — +12 tests: alignment layer counting, dedupe/partial-expiry/window-reset, model layer, analyst.trigger persist
- After T05: **545 passed, 5 skipped**, ruff clean, alembic head 024 (2026-07-02) — +20 tests: data-api normalizers, whale qualification boundaries, position diff add/exit/flip, end-to-end whale_delta→scorer
- After T06: **555 passed, 5 skipped**, ruff clean (2026-07-02) — +10 tests: news-lag boundaries (priced-in/unpriced/stale/low-relevance/neutral), end-to-end news_arrival persist
- After T07: **567 passed, 5 skipped**, ruff clean, alembic head 025 (2026-07-02) — +12 tests: brief schema validation, fallback generator, citation-required rejection, cooldown, deterministic claim
- After T08: **591 passed, 5 skipped**, ruff clean, alembic head 026 (2026-07-02) — +24 tests: 12-case claim matrix, epsilon boundary, no-lookahead negative control, metrics/provisional/Brier, citation audit
- After T09: **597 passed, 5 skipped**, ruff clean (2026-07-02) — +6 tests: alert fan-out, disabled-flags-no-external-calls, telegram/webhook transport, dedupe
- After T10: **604 passed, 5 skipped**, ruff clean (2026-07-02) — +7 tests: market ranking, top-N selection, digest assembly, idempotent-per-day
- After T11: **615 passed, 5 skipped**, ruff clean, alembic head 027 (2026-07-02) — +11 tests: model registry fallback, SHAP-or-fallback explanations; existing ml/predictor baseline preserved
- After T12: **625 passed, 5 skipped**, ruff clean (2026-07-02) — +10 tests: public API feed/track-record/claims/latency, pagination bounds, filters, 404
- After T13 (partial): **646 passed, 5 skipped**, ruff clean (2026-07-02) — +16 tests: taxonomy/score/persistence; Cursor FAIL on missing diff-engine/forecasting/rolling-score/AutoLab
- After T13 (v1): **641 passed, 5 skipped** — under-built, Cursor FAILed (spec gaps)
- After T13 rebuild + T14 completion: **669 passed, 5 skipped**, ruff clean (2026-07-02) — T13: 15-cat taxonomy, per-region rolling-decay 0-100, instability_shift DeltaEvent→alignment, forecasting features (flag-gated, NBA never); T14: daily_brief.py per-market assembly + markdown/compact formatters + distribution metadata. Both re-flipped IN-REVIEW.
- AutoLab (T13): baseline=election-class walk-forward Brier/CLV flag OFF (preserved) | benchmark=flag ON | iterations=0 (no labeled election snapshot dataset in env) | budget=0/8 | outcome=stalled — code merged flags OFF per spec.
- Stream latency (exchange→hub): StreamEvent.latency_ms exposes exchange→received; parse→publish path is I/O-free, asserted <50ms in test_kalshi_ws.py; pending live measurement
- Analyst brief latency: not yet measured
- Walk-forward Brier/CLV baseline (for T11 AutoLab): not yet measured

## Loop B log

- 2026-07-02 Cursor iter 1: no IN-REVIEW; claimed C3; gate green (C3 tests + ruff); T01 still CLAIMED-OPUS.
- 2026-07-02 Cursor iter 2 (heartbeat): no IN-REVIEW; claimed C4; `scripts/record_ws_fixtures.py` + 4 format tests green; T01 still CLAIMED-OPUS.
- 2026-07-02 Cursor iter 3 (heartbeat): no IN-REVIEW; C5 explorer-notes updated; stream subset 35 passed; T01 looks ready for Opus to flip IN-REVIEW.
- 2026-07-02 Cursor iter 4 (heartbeat): idle — no IN-REVIEW; C1/C2 blocked on Opus sign-off; C3–C5 done; waiting on Opus for T01 handoff.
- 2026-07-02 Cursor iter 5 (heartbeat): still idle; T01 unchanged CLAIMED-OPUS; base stream tests green.
- 2026-07-02 Cursor iter 6 (heartbeat): no state change; Loop B blocked on Opus T01 handoff.
- 2026-07-02 Cursor iter 7 (heartbeat): still idle; planner added T13+T14 to queue; T01 still CLAIMED-OPUS.
- 2026-07-02 Cursor iter 8 (heartbeat): no change; still blocked on Opus T01 → IN-REVIEW.
- 2026-07-02 Cursor iter 9 (heartbeat): T01 IN-REVIEW verify — gate 477p/5s green; **FAIL** 3 findings (missing accept tests + main.py stream task no-restart); T01 → CLAIMED-OPUS.
- 2026-07-02 Cursor iter 10 (heartbeat): T01 re-review **PASS** + T02 verify **PASS**; gate 498p/5s; T01+T02 → DONE; T03 CLAIMED-OPUS.
- 2026-07-02 Cursor iter 11 (heartbeat): T03+T04 verify **PASS**; gate 525p/5s; T03+T04 → DONE (**4/12**); T05 CLAIMED-OPUS.
- 2026-07-02 Cursor iter 12 (heartbeat): idle — no IN-REVIEW; T05 CLAIMED-OPUS; C1/C2 blocked on Opus sign-off.
- 2026-07-02 Cursor iter 13 (heartbeat): T05+T06 verify **PASS**; gate 555p/5s; **6/12** DONE; T07 CLAIMED-OPUS; T13 eligible.
- 2026-07-02 Cursor: T07 verify **PASS**; gate 567p/5s; **7/14** DONE; T08 CLAIMED-OPUS.
- 2026-07-02 Cursor iter 14 (heartbeat): idle — T08 CLAIMED-OPUS; T07 analyst subset 12 passed.
- 2026-07-02 Cursor iter 15 (heartbeat): T08 verify **PASS**; gate 597p/5s; **8/14** DONE; T09 CLAIMED-OPUS.
- 2026-07-02 Cursor iter 16 (heartbeat): T09+T10 verify **FAIL** — pytest 604p/5s green but ruff red (`trainer.py:8` unused import, T11 WIP); back to CLAIMED-OPUS for gate fix.
- 2026-07-02 Cursor iter 17 (heartbeat): T09 re-verify **PASS** (6 alert tests + ruff clean); T10 **PASS** (7 research tests); T11 **PASS** (25 ml tests, migration 027 chains 026, honest AutoLab iterations=0, default xgboost preserved). Full gate 623p/5s/2 failed — T12 WIP (`test_briefs_api` MissingGreenlet + rate-limit assert). **11/14** DONE; T14 now eligible; T12 still CLAIMED-OPUS.
- 2026-07-02 Cursor iter 18 (heartbeat): T12 verify **PASS** — 10 briefs_api tests; full gate **625p/5s** ruff clean; selectinload fix confirmed; rate-limit test corrected to reachability (acceptable vs spec header nit). **12/14** DONE; T13 CLAIMED-OPUS; T14 eligible for Opus.
- 2026-07-02 Cursor iter 19 (heartbeat): T13 verify **FAIL** — gate **646p/5s** ruff clean; license clean-room **PASS** (no AGPL code); 16 instability tests pass. **CONFIRMED gaps vs spec:** (1) no `event_taxonomy.py` / 15-category enum; (2) no per-region rolling decayed 0–100 score; (3) no `instability_shift` DeltaKind → diff engine; (4) no forecasting feature wiring + `test_instability_feature.py`; (5) no AutoLab baseline line in Metrics. Guardrails OK (headline_eligible=False, not alignment layer, flag OFF). T13 → CLAIMED-OPUS for fixes; T14 still CLAIMED-OPUS.
- 2026-07-02 Cursor iter 20 (heartbeat): T14 verify **FAIL** — gate **646p/5s** ruff clean; MIT attribution **PASS**; 5 digest_distribution tests pass; no order/TA code. **CONFIRMED gaps:** (1) no `daily_brief.py` per-market assembly (price/model/edge/CLV/news/whale); (2) no `daily_brief_markdown()`/`daily_brief_compact()` dual formatters; (3) no distribution metadata on digest row; (4) disabled test lacks mock-transport assert (non-blocking). Delivery pipe (T10 summary → T09 dispatch, flag OFF, per-day dedupe) works. **12/14** DONE; T13+T14 back to Opus.
- 2026-07-02 Cursor iter 21 (heartbeat): T13 re-verify **PASS** (44 scoped tests incl taxonomy/decay/threshold/instability_shift/features); T14 re-verify **PASS** (daily_brief assembly + markdown/compact + dist metadata). Full gate **669p/5s** ruff clean. License: T13 clean-room PASS; T14 MIT PASS. **14/14 T-tickets DONE.** Remaining: chores C1/C2 (Opus sign-off), final review §6.
- 2026-07-02 Cursor iter 22 (heartbeat): idle — no IN-REVIEW; all T01–T14 DONE; C1/C2 blocked on Opus sign-off; last gate **669p/5s** green.
- 2026-07-02 Cursor iter 23 (heartbeat): **loop complete** — §6 final review PASS; C1/C2 DEFERRED per Opus sign-off; no further Loop B work. Heartbeat not re-armed.
- 2026-07-02 Post-loop review fixes (Claude, /code-review follow-up): (1) `get_market_history` gate fixed — Kalshi live markets no longer 404 (now uses `_is_accessible_mirror_market`); (2) whale connector live-verified and fixed — leaderboard moved to real `lb-api.polymarket.com/profit` (data-api/leaderboard is 404), qualification source switched from `/trades` (no pnl/resolved fields live) to `/closed-positions` (has realizedPnl) with offset pagination past the 50-row page cap; verified live: real whale qualified (resolved=200, acc=1.00), others rejected with correct reasons; (3) lightgbm 4.6.0 + shap 0.51.0 now INSTALLED (ml-extra) — registry builds LGBMClassifier, 19 ML tests pass under ML_MODEL_TYPE=lightgbm; the T11 Brier A/B on real data is now runnable and remains for a future loop. Gate after fixes: **669p/5s** ruff clean.
