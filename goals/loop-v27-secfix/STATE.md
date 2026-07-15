# Loop V27 — STATE
| ID | Ticket | Status | Notes |
|----|--------|--------|-------|
| X1 | SEC-Z2-01 followed-trade notify | DONE | `follows` detected; paper fill fans `notify_followers_of_paper_trade` |
| X2 | SEC-Z2-02 read-all staleness | DONE | `mark_all_read` updates ORM instances (identity map coherent) |
| X3 | SEC-Z1-01 admin 5xx | DONE | body requires `source`; empty matrix → blocked 200, never KeyError |
| X4 | Gate + zero-xfail confirm | DONE | 1572 passed / 28 skipped / 0 xfailed; verifier PASS |

## SHARED FILE CLAIMS
| File | Ticket | Status |
|---|---|---|
| backend/app/services/notification_producers.py | X1 | DONE |
| backend/app/api/v1/orders.py | X1 | DONE |
| backend/tests/test_loop26_social_notify_journeys.py | X1+X2 | DONE |
| backend/tests/test_notification_producers.py | X1 | DONE |
| backend/app/services/notification_service.py | X2 | DONE |
| backend/app/admin/routes.py | X3 | DONE |
| backend/app/schemas/market.py | X3 | DONE |
| backend/app/backtesting/replay.py | X3 | DONE |
| backend/tests/test_loop26_authz_matrix.py | X3 | DONE |
| backend/tests/test_worker_snapshot_capture.py | X3 | DONE |

## LOOP LOG

### X1 — 2026-07-14 — DONE
- `social_follow_tables_present()` includes mapped table `follows`.
- Paper BUY + CLOSE call `notify_followers_of_paper_trade` after `notify_order_filled` (never-raises).
- Un-xfail `test_z2_followed_trade_notification_gap`.
- Commit: `f7807a9 fix(loop27): SEC-Z2-01`

### X2 — 2026-07-14 — DONE
- `mark_all_read` sets `read_at` on ORM instances (identity map coherent for subsequent list).
- Un-xfail item-level assert in `test_z2_notification_read_and_read_all`.
- Commit: `e6c60dd fix(loop27): SEC-Z2-02`

### X3 — 2026-07-14 — DONE
- `Phase3SnapshotStoreBacktestRequest` requires `source` → empty `{}` is 422.
- Empty / missing-`captured_at` matrix returns blocked gate (never KeyError).
- Removed SEC-Z1-01 from `_XFAIL_PROBES`.
- Happy-path admin test posts `{"source":"snapshot_store"}`.
- Commit: `846bf01 fix(loop27): SEC-Z1-01`

### X4 — 2026-07-14 — DONE
Full gate (fresh):
```
ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q -p no:cacheprovider
→ 1572 passed, 28 skipped in 495.99s (0:08:15)   # 0 xfailed
uv run --extra dev ruff check app tests → All checks passed!
```
Loop26 modules only:
```
tests/test_loop26_authz_matrix.py
tests/test_loop26_social_notify_journeys.py
tests/test_loop26_admin_journeys.py
tests/test_loop26_negative_abuse.py
→ 16 passed in 52.60s
```
SEC marker check:
```
rg -n "xfail|skip" backend/tests -g "*.py" | rg -i "SEC-"
→ NO xfail/skip lines also matching SEC-
```
(Residual defensive `pytest.xfail` in Z4 abuse suite only fires if a new 5xx appears; not open known-defect markers for Z1/Z2.)

## Adversarial verifier verdict (fresh subagent, read-only)
- **VERDICT: PASS**
- Must-fix: none
- Scope: backend services/routes/schemas/tests + goals/loop-v27-secfix only
- PAPER_TRADING_ONLY intact; order path additive never-raises observation hooks only
- No frontend/deploy edits; no push/merge
- Claims X1–X3 evidenced at file:line in verifier report
- Nits (non-blocking): optional dedicated empty-body 422 unit test; mark_all_read loads all unread (scale)

## Commits
```
846bf01 fix(loop27): SEC-Z1-01
e6c60dd fix(loop27): SEC-Z2-02
f7807a9 fix(loop27): SEC-Z2-01
```

AutoLab: not applicable (no iterative measure)
