# Loop V27 — STATE
| ID | Ticket | Status | Notes |
|----|--------|--------|-------|
| X1 | SEC-Z2-01 followed-trade notify | DONE | `follows` detected; paper fill fans `notify_followers_of_paper_trade` |
| X2 | SEC-Z2-02 read-all staleness | DONE | `mark_all_read` updates ORM instances (identity map coherent) |
| X3 | SEC-Z1-01 admin 5xx | DONE | body requires `source`; empty matrix → blocked 200, never KeyError |
| X4 | Gate + zero-xfail confirm | TODO | |

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

### X2 — 2026-07-14 — DONE
- `mark_all_read` sets `read_at` on ORM instances (identity map coherent for subsequent list).
- Un-xfail item-level assert in `test_z2_notification_read_and_read_all`.
- Gate: 1572 passed, 28 skipped; ruff All checks passed.

### X3 — 2026-07-14 — DONE
- `Phase3SnapshotStoreBacktestRequest` requires `source` → empty `{}` is 422.
- Empty / missing-`captured_at` matrix returns blocked gate (never KeyError).
- Removed SEC-Z1-01 from `_XFAIL_PROBES`.
- Happy-path admin test posts `{"source":"snapshot_store"}`.
- Gate:
```
ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q -p no:cacheprovider
→ 1572 passed, 28 skipped in 358.52s (0 xfailed)
uv run --extra dev ruff check app tests → All checks passed!
```
- Focused: matrix + phase3 admin happy path → 3 passed.
