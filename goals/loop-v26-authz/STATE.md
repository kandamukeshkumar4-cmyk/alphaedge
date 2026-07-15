# Loop V26 — STATE
| ID | Ticket | Status | Notes |
|----|--------|--------|-------|
| Z1 | AuthZ matrix | DONE | `tests/test_loop26_authz_matrix.py` — 154 paths / 167 ops; AUTH_CLASS from router Depends; 3 actors; no 5xx |
| Z2 | Social+notify journeys | DONE | `tests/test_loop26_social_notify_journeys.py` — feed journey green; 2 xfail SECs |
| Z3 | Admin journeys | DONE | `tests/test_loop26_admin_journeys.py` — suspend/pause/stats-cache |
| Z4 | Negative/abuse | DONE | `tests/test_loop26_negative_abuse.py` — IDOR + garbage/oversize 4xx |

## SEC REPORTS (findings — do not fix here)

### SEC-Z1-01 — admin phase3 snapshot backtest uncaught KeyError
- **Route:** `POST /admin/phase3-snapshot-store-backtests`
- **Auth:** admin (`X-Admin-API-Key: dev-admin-key`)
- **Payload:** `{}` (empty body)
- **Observed:** uncaught `KeyError: 'captured_at'` (propagates as exception under ASGI test client; ≈ 5xx in real deploy)
- **Expected:** 4xx validation or 2xx empty-result, never uncaught exception
- **Matrix handling:** soft-checked via `_XFAIL_PROBES` in `test_loop26_authz_matrix.py`

### SEC-Z2-01 — followed_trade notification never produced
- **Route journey:** `POST /api/v1/social/follow/{trader}` (user A) → `POST /api/v1/orders` (user B) → `GET /api/v1/notifications` (user A)
- **Auth:** A and B Bearer JWTs
- **Payload (B order):** `{"slug":"nba-2025-01-15-lal-bos","side":"YES","shares":2,"price":0.5}`
- **Observed:** A’s notification list has no `type=followed_trade` (B’s own `order_filled` may exist for B only). Root cause: (1) paper order path calls `notify_order_filled` only — never `notify_followed_trader_trade`; (2) `social_follow_tables_present()` checks for `{trader_follows,user_follows,social_follows}` but mapped table is `follows` → always False
- **Expected:** A receives in-app notification that B traded
- **Test:** `test_z2_followed_trade_notification_gap` xfails with this SEC id

### SEC-Z2-02 — mark_all_read leaves stale unread flags on listed rows
- **Route:** `POST /api/v1/notifications/read-all` then `GET /api/v1/notifications`
- **Auth:** Bearer JWT owner
- **Payload:** none
- **Observed:** `unread_count` (SQL) becomes 0, but item `unread` may still be `true` because `mark_all_read` uses `update(...).execution_options(synchronize_session=False)` and the shared session identity map is not refreshed (`expire_on_commit=False` in tests)
- **Expected:** listed items reflect `read_at` after read-all in the same request path
- **Test:** `test_z2_notification_read_and_read_all` xfails item-level check when stale

### Surprising public surfaces (not defects per se — documented from AUTH_CLASS)
- Paper-token routes classified **public** (no JWT): `GET /api/v1/orders`, `POST /api/v1/markets/{slug}/orders`, `POST /api/v1/orders/{order_id}/cancel`, `GET /api/v1/accounts/{account_id}/positions`, `GET /api/v1/paper-account` — gated by `X-Paper-Account-Token` / shared-account exception in local env
- `GET /api/v1/forecasters/me/*` public path names (forecaster cookie/session separate from JWT)
- `POST /api/v1/telemetry/mirror/events` public

### Pre-existing gate noise (not introduced by loop26)
- `tests/test_daily_digest.py::{test_digest_idempotent_per_user_per_day,test_run_daily_digest_batch}` fail when calendar day ≠ hard-coded `date(2026, 7, 14)` because idempotency windows on `Notification.created_at` vs now. Repro on 2026-07-15 UTC: second digest creates again. **Not modified** (never weaken existing tests; not app fix in this loop).

## LOOP LOG

### Z1 — 2026-07-15
- Built `AUTH_CLASS` by walking FastAPI route `Depends` (`verify_admin_api_key` / `get_current_user` / `get_optional_user` + `/metrics` inline gate).
- Counts: public=88, admin=39, user=36, optional_user=3, admin_metrics=1 (167 ops / 154 paths).
- Gate (loop26 module): `2 passed` in ~31s.
- Full suite (this worktree): **1556 passed, 28 skipped, 2 failed** (digest date hardcode only) + ruff All checks passed.
- Verifier: see bottom.

### Z2 — 2026-07-15
- Journeys: follow→trade→feed OK; opt-out hides profile+feed; read/read-all; fake-WS notifications frame OK.
- Xfail SEC-Z2-01, SEC-Z2-02.

### Z3 — 2026-07-15
- Suspend→403 order→unsuspend→201; pause→reject→unpause→201; DomainEvent audits; stats cache True→invalidate→users++.

### Z4 — 2026-07-15
- IDOR: notifications/portfolio/clones/watchlist/admin-users; paper-account tokenless foreign UUID 401.
- Garbage/oversize mutating probes never 5xx.

### Loop26 combined module gate
```
ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q -p no:cacheprovider \
  tests/test_loop26_authz_matrix.py tests/test_loop26_social_notify_journeys.py \
  tests/test_loop26_admin_journeys.py tests/test_loop26_negative_abuse.py
→ 14 passed, 2 xfailed in 63.44s
ruff check tests/test_loop26_*.py → All checks passed!
```

### Full backend gate tail (Z1 full run; digest pre-existing)
```
FAILED tests/test_daily_digest.py::test_digest_idempotent_per_user_per_day
FAILED tests/test_daily_digest.py::test_run_daily_digest_batch
2 failed, 1556 passed, 28 skipped in 523.96s
ruff check app tests → All checks passed!
```

### Adversarial verifier verdict
- **Scope compliance:** PASS — only new files under `backend/tests/test_loop26_*.py` + `goals/loop-v26-authz/STATE.md`; no app/frontend/deploy edits; existing tests untouched.
- **Auth matrix honesty:** PASS — table committed, snapshot coverage asserted (154/167), cookie cleared so anon is real; expected codes per class.
- **No silent greenwash:** PASS — app defects captured as SEC-* with repro; xfail/skip references SEC ids.
- **Order path / paper-only:** PASS — journeys use paper orders only; no live execution language.
- **Gate:** Loop26 modules green; full suite has pre-existing digest date failures unrelated to this loop (documented).
- **VERDICT: PASS for Z1–Z4 ticket goals (tests-only).** Residual SECs deferred to app-code owners.
