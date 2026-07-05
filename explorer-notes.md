# Explorer notes — project completion vs original architecture

## Files to change
- None for this audit (read-only). **Doc hygiene only if desired:** `goals/loop-x-mirror-mvp.md` frontmatter `status: QUEUED` vs `goals/README.md` ✅ DONE; `goals/phase-fifa-wc2026.md` `status: ACTIVE` vs README ✅ DONE; `docs/project/QUANT_ROADMAP.md` header still `Status: plan`.

## Tests to run
- `cd backend && uv run --extra dev pytest -q` — **434 passed, 4 skipped** (verified 2026-06-12, ~7.5 min)
- `cd backend && uv run --extra dev ruff check app tests`
- `cd frontend && npm run lint && npm run typecheck && npm run build`
- `cd extension && npm test && npm run typecheck && npm run build`
- CI: `.github/workflows/ci.yml` (backend + frontend + extension on push/PR)

## Original plan sources (summary)
| Source | Scope |
|---|---|
| `README.md` L109–121 | Week 1–5 architecture: CLOB→Backtest→XGBoost→Eval→Risk→Agents; deploy Week 5 |
| `AGENTS.md` L20–26 | Execution Gates Week 1–5 (canonical verification claims) |
| `docs/project/QUANT_ROADMAP.md` | Quant phases 0–6 + optional Phase 5 MM; CLV gate; authored 2026-06-04 |
| `goals/README.md` | Execution queue — **all rows ✅ DONE except Phase 5 🅿️ DEFERRED**; no ACTIVE goal |
| `docs/superpowers/plans/2026-05-29-alphaedge-week1-base.md` | Week 1 base plan (historical) |
| `docs/project/CURSOR_2_5_TASKS.md` | Week 1 gate first; later weeks scaffold until proven |

## DONE vs remaining (by pillar)
| Pillar | Status | Evidence |
|---|---|---|
| **Backend CLOB/ledger** | DONE (Week 1) | `order_book.py`, `ledger_service.py`, `test_orderbook_lakers_celtics.py`, `test_orderbook_engine.py` |
| **Workers/fixtures/ML** | DONE (Week 2+) | `workers/`, `ml/features.py`, `trainer.py`, `test_backtest_smoke.py`, `test_worker_snapshot_capture.py` |
| **Eval/Brier/calibration/risk** | DONE (Week 3) | `eval/`, `api/v1/calibration.py`, `test_eval_service.py`, `test_risk.py`, `test_calibration.py` |
| **Agents/LangGraph** | DONE (Week 4) | `agents/graph.py` calls `predict_market` (no `+0.03` stub); `test_agents.py`, `admin/proof` page |
| **Deploy/CI** | DONE (Week 5) | `ci.yml`, Railway/Koyeb/HF/Azure workflows, `test_deploy_config.py`, live HF API in README |
| **Quant Phase 0–4, 6** | DONE | connectors, signals, smart_money, predictor+CLV gate, `llm/`, overlay/dashboard per goals |
| **FIFA WC2026 track** | DONE (per README) | `data/fifa/`, `test_fifa_*`, `test_wc2026_*` |
| **Loops X/Y (Mirror, sell/close)** | DONE (per README) | `test_mirror_*`, `test_position_close.py`, `frontend/src/app/mirror/page.tsx` |
| **Phase 5 market making** | DEFERRED | `goals/README.md` only; no implementation |
| **Election markets** | Partial | Catalog seeds in `market_service.py`; no election forecast engine like NBA/FIFA |

## Risks
- `PAPER_TRADING_ONLY=true` enforced (`test_config.py`); order path `RiskService → OrderIntent → OrderBookService` (`test_order_api_risk_gate.py`, `test_agents.py`).
- CLV gate is test/fixture-proven; **live OOS edge vs real closing lines unverified** in docs.
- Goal frontmatter stale vs `goals/README.md` — treat README table as canonical queue state.
- FanDuel explicitly deferred per Loop X gate.

## Do not touch
- Order path guardrails, `PAPER_TRADING_ONLY` enforcement, CLV hide-non-edge behavior.
- Optional Phase 5 market-making (explicitly deferred until opt-in).

## Verdict
**~92–95% of mandatory planned scope complete.** Original Week 1–5 architecture and Quant phases 0–4/6 (+ FIFA, Mirror loops) are implemented with broad test coverage. **Only optional Phase 5 (market making) remains explicitly out of scope.** Honest uncertainty: production CLV edge on live data, election forecasting depth, and doc/goal-status drift. **No ACTIVE goal in queue** — project is in maintenance/iteration mode (e.g. `calibration-autolab.yml`), not greenfield build.

## PolyScout build loop (2026-07-02)
Spec: `docs/project/BUILD_LOOP_BACKEND.md` · State: `goals/build-loop/STATE.md`

| Area | Status |
|---|---|
| T01 Kalshi WS stream | In progress (`CLAIMED-OPUS`) — `app/data/streams/{base,kalshi_ws,runner}.py`, `persist_and_publish_tick` shared with poller |
| C3 Prometheus `/metrics` | DONE — `prometheus-client` counters (stream events, briefs, claims, WS clients) |
| C4 WS fixture recorder | DONE — `scripts/record_ws_fixtures.py` → JSONL for offline parser tests |
| T02–T12 | QUEUED |

Targeted gate (stream + metrics chores): **35 passed** (2026-07-02 Cursor). Full `pytest -q` still slow/hangs ~30% — bisect pending.

---

## PolyScout backend build loop — COMPLETE (2026-07-02, Opus builder + Cursor verifier)

All 14 T-tickets DONE (Cursor-verified). Final gate: **669 passed, 5 skipped, ruff
clean, single alembic head 027** (chain 022→027). Baseline 434 → 669 (+235 tests).

Delivered (the AI research desk, "PolyScout"):
- **T01/T02** Kalshi + Polymarket CLOB WebSocket streams → shared tick path.
- **T03** snapshot diff engine (price/orderbook/volume DeltaEvents).
- **T04** alignment scorer — ≥3-of-4 layers agree → `analyst.trigger`.
- **T05** whale tracker (data-api qualification + position-diff whale_delta).
- **T06** news→price lag detector (unpriced-headline signal).
- **T07** analyst agent — LangGraph, cited briefs + deterministic falsifiable claims,
  runs with NO LLM key (fallback).
- **T08** eval harness — no-lookahead claim grading + public track record (accuracy/
  Brier by category/version, provisional<30) + citation audit. The hire-signal.
- **T09** alert dispatch (WS/Telegram/webhook, OFF by default).
- **T10** scheduled research loop (daily digest, idempotent).
- **T11** LightGBM registry + SHAP-or-fallback explanations (honest AutoLab: infra
  ready, A/B deferred — libs uninstallable here).
- **T12** public API — `/briefs`, `/analyst/track-record`, `/markets/{slug}/latency`
  (the UI-loop contract).
- **T13** instability signal (clean-room, AGPL-free; flag-gated).
- **T14** daily brief distribution (MIT-attributed).

Guardrails intact: `PAPER_TRADING_ONLY` enforced; no new module touches the order
path (RiskService→OrderIntent→OrderBookService); no keys committed; license
compliance (clean-room AGPL, MIT attribution) verified.

Chores: C3–C5 DONE; **C1/C2 DEFERRED** (Opus sign-off — PaperOrder/PaperSignal are
active, tested, guardrail-critical models with 42/28 refs; consolidation is risk
without benefit).

**UI is OUT OF SCOPE** — a separate `BUILD_LOOP_UI.md` consumes the T12 API contract.
State spine: `goals/build-loop/STATE.md`.
