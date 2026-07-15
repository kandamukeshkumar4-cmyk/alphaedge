# Loop V27 — STATE
| ID | Ticket | Status | Notes |
|----|--------|--------|-------|
| X1 | SEC-Z2-01 followed-trade notify | DONE | `follows` detected; paper fill fans `notify_followers_of_paper_trade` |
| X2 | SEC-Z2-02 read-all staleness | DONE | `mark_all_read` updates ORM instances (identity map coherent) |
| X3 | SEC-Z1-01 admin 5xx | TODO | |
| X4 | Gate + zero-xfail confirm | TODO | |

## SHARED FILE CLAIMS
| File | Ticket | Status |
|---|---|---|
| backend/app/services/notification_producers.py | X1 | DONE |
| backend/app/api/v1/orders.py | X1 | DONE |
| backend/tests/test_loop26_social_notify_journeys.py | X1+X2 | DONE |
| backend/tests/test_notification_producers.py | X1 | DONE |
| backend/app/services/notification_service.py | X2 | DONE |

## LOOP LOG

### X1 — 2026-07-14 — DONE
- `social_follow_tables_present()` now includes mapped table `follows`.
- Paper BUY + CLOSE paths call `notify_followers_of_paper_trade` after `notify_order_filled` (never-raises).
- Un-xfail `test_z2_followed_trade_notification_gap`.
- Gate: ruff All checks passed; loop26 social+matrix 6 passed, 1 xfailed (Z2-02 only).

### X2 — 2026-07-14 — DONE
- `mark_all_read` loads unread rows and sets `read_at` on ORM instances (no bulk UPDATE with `synchronize_session=False`).
- Un-xfail item-level assert in `test_z2_notification_read_and_read_all`.
- Gate:
```
ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q -p no:cacheprovider
→ 1572 passed, 28 skipped in 389.45s (0 xfailed journey SECs)
uv run --extra dev ruff check app tests → All checks passed!
```
- Focused: `test_z2_notification_read_and_read_all` → 1 passed.
