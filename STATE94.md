# STATE94 — skill/scanner marketplace maturity (BACKEND)

Loop: V94 | Seat: EXECUTOR | Worktree: `E:/polymarket-worktrees/loop94-marketplace`

## Status

| Ticket | Status |
|--------|--------|
| M1 migration + models | DONE |
| M2 rate endpoints | PENDING |
| M3 trending | PENDING |
| M4 featured | PENDING |

## Assumptions

- `trending_score = recent_7d_runs + avg_rating` (weight 1.0). Skills have no per-run log → use `Skill.run_count` as the run signal.
- Scanners: recent runs = `ScannerRun.started_at` in `[now-7d, now]` (reference time passed into pure ranking fn).
- Feature toggle body: `{"is_featured": bool}`; auth = `X-Admin-API-Key` via `verify_admin_api_key`.
- Migration head was `062_notif_engagement` → `063_marketplace_ratings` (23 chars).

## LOOP LOG

### M1 — migration + models

```
git log -1 --oneline
(pending commit below)
```

pytest:
```
...                                                                      [100%]
3 passed in 55.10s
```

ruff: All checks passed!
