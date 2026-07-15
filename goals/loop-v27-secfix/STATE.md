# Loop V27 — STATE
| ID | Ticket | Status | Notes |
|----|--------|--------|-------|
| X1 | SEC-Z2-01 followed-trade notify | DONE | `follows` detected; paper fill fans `notify_followers_of_paper_trade` |
| X2 | SEC-Z2-02 read-all staleness | TODO | |
| X3 | SEC-Z1-01 admin 5xx | TODO | |
| X4 | Gate + zero-xfail confirm | TODO | |

## SHARED FILE CLAIMS
| File | Ticket | Status |
|---|---|---|
| backend/app/services/notification_producers.py | X1 | DONE |
| backend/app/api/v1/orders.py | X1 | DONE |
| backend/tests/test_loop26_social_notify_journeys.py | X1 | DONE (Z2-01 un-xfail; Z2-02 still xfail) |
| backend/tests/test_notification_producers.py | X1 | DONE |

## LOOP LOG

### X1 — 2026-07-14 — DONE
- `social_follow_tables_present()` now includes mapped table `follows`.
- Paper BUY + CLOSE paths call `notify_followers_of_paper_trade` after `notify_order_filled` (never-raises).
- Un-xfail `test_z2_followed_trade_notification_gap`.
- Gate:
```
ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q -p no:cacheprovider
→ exit 0; ~1570+ passed / 28 skipped / remaining journey xfail = SEC-Z2-02 only
  (loop26 social+matrix: 6 passed, 1 xfailed in 42.11s)
uv run --extra dev ruff check app tests → All checks passed!
```
- Focused: followed_trade + tables present + paper order notify → 3 passed.
