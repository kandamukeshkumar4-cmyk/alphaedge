# Loop V19 — STATE
| ID | Ticket | Status | Notes / verification evidence |
|----|--------|--------|------------------|
| W1 | API reference | DONE | `docs/api.md` — 111 table paths verified vs openapi_snapshot (131) + code; verifier PASS |
| W2 | User guide | TODO | |
| W3 | Operations runbook | TODO | |
| W4 | Model methodology | TODO | |
| W5 | README refresh | TODO | |

## LOOP LOG (append per iteration; list endpoint/flag verifications)

### W1 — API reference (2026-07-14)

**Deliverable:** `docs/api.md`

**Verification evidence (each claim checked):**

| Claim | Verified via |
|-------|----------------|
| OpenAPI snapshot has 131 path keys (not nested under `paths`) | `backend/tests/fixtures/openapi_snapshot.json` JSON top-level keys |
| `GET /api/v1/markets` supports `sort=active` | `routes.py` `_VALID_SORTS = {"volume", "traders", "newest", "active"}` |
| Auth signup/login/logout/me/patch | `api/v1/auth.py`; cookie `ae_access` + Bearer in `deps.py` |
| Human paper `POST /api/v1/orders` + `Idempotency-Key` | `api/v1/orders.py` Header alias; dual-ledger docstring |
| Human close `POST /api/v1/positions/close` + Idempotency-Key | same file |
| CLOB place/cancel + RiskService | `routes.py` `place_order` / `cancel_order`; cancel 403/409/404 |
| Portfolio suite (summary/risk/attribution/equity-curve/exposure/clv) | `portfolio.py`, `portfolio_clv.py`; all JWT `get_current_user` |
| Leaderboard | `leaderboard.py` mounted under v1; `sort`/`limit`/`offset` |
| Activity trades + signals/events + alerts | `activity.py` |
| Watchlist JWT CRUD | `watchlist.py` |
| Eval evaluations/aggregates/calibration | `eval_routes.py` prefix `/api/v1/eval` |
| Drift under admin observability (not `/eval/drift`) | `observability.py` `/api/v1/admin/observability/drift` |
| System loops / metrics / resolved-count / model-ab | `system.py` |
| System sources admin | `sports.py` `sources_router` prefix `/api/v1/system` + `verify_admin_api_key` |
| WS `/api/v1/ws/feed` channels: briefs, alerts, feed, activity + bus topics | `ws.py` `_FEED_TOPICS`, `_BUS_TOPICS` |
| WS `/api/v1/ws/prices` | `ws.py` |
| Prometheus `/metrics` admin/token gated | `observability/metrics.py` |
| Admin markets/agents | `admin/routes.py`, `admin/agent_routes.py` |
| PAPER_TRADING_ONLY on trading + WS | `orders.py`, `ws.py` |
| No secret values in doc | manual review |

**Adversarial verifier:** `goals/loop-v19-docs/_verify_api_paths.py` → `table_paths=111` all found in snapshot or code → **PASS**. Explicitly confirmed fabricated `/api/v1/eval/drift` is **documented as non-existent**.

**Gate:** docs-only; relative links self-contained; no app code edits.
