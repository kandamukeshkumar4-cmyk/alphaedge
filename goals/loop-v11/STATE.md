# Loop V11 — Security-audit remediation (2026-07-10)

> Special loop: ships a pre-existing, complete security-audit change that was
> found uncommitted in the working tree. Orchestrator verifies, gates, gets a
> fresh-context verifier verdict, commits, deploys, verifies prod.

## WHY

A security audit produced a coherent remediation (tagged findings below) that
was sitting uncommitted. It hardens auth on compute-heavy endpoints, fixes a
paper-balance race on order-close, and makes the admin-key check timing-safe.
High value; complete (backend + migration + frontend + tests). Ship it.

## SCOPE (the audit findings)

- **H-SEC-03** — `POST /api/v1/analyst/run` (LLM run + market auto-create) now
  requires JWT auth (was anonymous → cost-abuse / market-pollution risk).
- **M-SEC-01** — `POST /api/v1/backtest/run` (sync compute-heavy replay) now
  requires JWT auth (DoS risk). Distinct from the public `GET /backtest/run`
  self-serve (V6 K01) — same path, different verb, they coexist.
- **H-RACE-02** — order-close balance credit is now atomic
  (`UPDATE User ... paper_balance + proceeds ... RETURNING`) mirroring the buy
  path, plus an **idempotency key** on close (`Idempotency-Key` header,
  dedupe on `(user, key)`, concurrent-close IntegrityError rollback+replay).
  New migration `037_paper_order_idempotency` (chains from `036_notify_prefs`).
- **Timing attack** — admin-key check uses `secrets.compare_digest`.
- **Info leak** — analyst/backtest error responses no longer echo raw
  exception strings.

Frontend: `orders-api.ts` sends `Idempotency-Key` (one key per trade intent);
trade/position components updated; analyst/backtest calls send the JWT.
`scripts/verify_journey.py` authenticates the analyst step + marks it write-only
on the readonly cron. Tests: `test_public_compute_auth.py` (new),
`test_position_close.py` (+cases), `orders-close.test.ts`.

## GUARDRAILS

- PAPER_TRADING_ONLY; RiskService order path untouched (this hardens the
  existing paper close path, does not add a new order route). Analysis-only
  endpoints stay analysis-only. No fabricated data. Never weaken a test.
- Behavioral change (intended): anonymous users can no longer trigger
  analyst/backtest runs — the deployed frontend sends the JWT.

## GATE (paste output)

- Backend: `ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q` + ruff;
  single Alembic head = `037_paper_order_idempotency`.
- Frontend: typecheck + lint + vitest + build.
- Fresh-context verifier re-runs the gate + reviews the diff vs guardrails.
- Post-deploy: `verify_prod.py` 6/6; probe `POST /analyst/run` + `POST
  /backtest/run` return 401 anon; `verify_journey.py` (authed) still green.

## LOOP LOG

| iter | date | ticket | result | proof |
|------|------|--------|--------|-------|
| 1 | 2026-07-10 | v11-security | VERIFIED, DEPLOY BLOCKED-ON-USER | Frontend gate green; fresh-context verifier PASS (race credits once, JWT wired, GET/POST backtest coexist, single head 037); security subset 15 passed. Committed to branch feat/security-audit-v11 (NOT deployed). BLOCKER: HF deploy requires GitHub secret JWT_SECRET_KEY (deploy workflow now require()s it); it is unset, and prod is currently running on the published default JWT secret (forgeable tokens) until it is set. AutoLab: not applicable (security remediation, no iterative metric).
| 2 | 2026-07-10 | v11-deploy | DONE — SHIPPED + VERIFIED | JWT_SECRET_KEY set by owner; deployed. verify_prod 6/6; POST /analyst/run + POST /backtest/run 401 anon; GET /backtest/run?slug= 200 public; authed journey step4 analyst brief generator=llm (auth works for logged-in). Deploy 'failure' = known assistant ReadTimeout smoke flake (real /health 200). Prod JWT no longer the forgeable default. Order 409 in journey step5 = pre-existing buy-path price-drift, not V11.
