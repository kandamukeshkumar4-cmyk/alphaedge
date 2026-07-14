# Loop V19 — Documentation & Launch Readiness

> Runner: Grok CLI #2 (headless), worktree E:/polymarket-worktrees/loop19-docs,
> branch loop19/docs. Orchestrator reviews every commit. Roadmap Phase 5 work.

## Mission
Ship the launch documentation set: accurate, verified-against-code, honest
about paper-trading-only. Everything you write must be checked against the
ACTUAL code/API responses (read the code, hit the local endpoints) — no
invented endpoints, no aspirational features, no fabricated numbers.

## Ownership (strict)
YOURS: docs/** (new files or updates), README.md (root + backend/ + frontend/).
FOREIGN — never edit: any app code (backend/app/**, frontend/src/**, e2e/**),
deploy configs, other goals/ folders, workflows.

## Guardrails
Every claim verified against code or a locally-run endpoint; PAPER_TRADING_ONLY
prominently stated; no marketing invention; no secrets/URLs with credentials in
docs; prod URLs OK (Railway API + Vercel app). Never push/merge/deploy.

## Gate (per ticket): docs build nothing — instead: (a) every documented
endpoint/flag verified to exist via grep or local GET (list the verification
in STATE.md), (b) markdown lint-clean (consistent headings, working relative
links), (c) fresh adversarial verifier verdict per ticket.

## Tickets (continuous, one commit each: docs(loop19): <ticket>)
- W1 API reference: docs/api.md — the real public surface (auth, markets incl.
  sort=active, trading/orders incl. Idempotency-Key + cancel semantics,
  portfolio suite incl. attribution/equity-curve/risk, leaderboard, activity,
  watchlist, signals/events, eval/drift, system/loops+sources+resolved-count,
  WS /api/v1/ws/feed channels). Derive from code + the OpenAPI snapshot
  (backend/tests/fixtures/openapi_snapshot.json); mark admin-gated endpoints.
- W2 User guide: docs/user-guide.md — signup, discover (trending vs
  Longshots/Decided), reading signals/briefs, placing paper trades, portfolio
  (P&L, equity curve, attribution), leaderboard, alerts; honest "how numbers
  accrue" section (forecasts lock pre-close, resolve from venue data, then
  grade — why track-record starts sparse).
- W3 Operations runbook: docs/operations.md — deploy path (railway up
  --path-as-root from loop3), env vars table (names + purpose only, NO values),
  migrations policy (single head, pre-deploy upgrade), monitoring (gated
  /metrics, demo-uptime cron, system/loops heartbeats, system/sources), the
  Neon->Railway migration story + rollback copy note.
- W4 Model methodology: docs/methodology.md — forecast engine honestly: XGBoost
  + calibration, walk-forward eval, Brier/ECE, leakage gate (no post-close
  training), drift detection thresholds, flag-gated retrain that never
  auto-activates; paper-simulation disclaimer.
- W5 README refresh: root README aligned to reality (Railway+Vercel stack, one
  quickstart that works: uv sync, docker-compose or local uvicorn, npm dev,
  test commands incl. npm run test:e2e), links to W1-W4.
