# STATE94 — skill/scanner marketplace maturity (BACKEND)

Loop: V94 | Seat: EXECUTOR | Worktree: `E:/polymarket-worktrees/loop94-marketplace`

## Status

| Ticket | Status | Commit |
|--------|--------|--------|
| M1 migration + models | DONE | `6cc8ac3` |
| M2 rate endpoints | DONE | `8cc2383` |
| M3 trending | DONE | `1f2b94d` |
| M4 featured | DONE | `199f25a` |

**BACKEND node: M1–M4 COMPLETE. STOP (no push/deploy).**

## Assumptions

- `trending_score = (recent_run_count * 1.0) + avg_rating`. Pure fn takes counts/rating only (no `time.now`).
- Skills have no per-run log → when `recent_run_count=0`, fall back to `Skill.run_count`.
- Scanners: recent = `ScannerRun.started_at` in `[now-7d, now]` (reference `now` set once in the route).
- Feature toggle: `POST /{id}/feature` + `{"is_featured": bool}` + `X-Admin-API-Key` (`verify_admin_api_key`).
- Migration: `062_notif_engagement` → `063_marketplace_ratings` (23 chars).

## Frozen contract delivered

- `POST /api/v1/skills/{id}/rate` → `{avg,count,my_stars}` (auth, upsert, 422 outside 1–5)
- `GET /api/v1/skills/trending?limit=10` → `{items:[SkillOut + avg_rating,rating_count,run_count,trending_score]}`
- `GET /api/v1/skills/featured` → `{items:[SkillOut...]}` (`is_featured=true`)
- Same three for scanners; plus admin `POST /{id}/feature`

## LOOP LOG

### M1 — migration + models

```
6cc8ac3 feat(loop94): M1 — marketplace ratings tables + is_featured
```

```
...                                                                      [100%]
3 passed in 55.10s
```

ruff: All checks passed!

### M2 — rate endpoints

```
8cc2383 feat(loop94): M2 — skill/scanner rate endpoints with upsert
```

```
.....                                                                    [100%]
5 passed in 11.49s
```

ruff: All checks passed!

### M3 — trending

```
1f2b94d feat(loop94): M3 — deterministic skills/scanners trending endpoints
```

```
..........                                                               [100%]
10 passed in 8.63s
```

ruff: All checks passed!

### M4 — featured

```
199f25a feat(loop94): M4 — featured lists + admin feature toggle
```

```
............                                                             [100%]
12 passed in 8.18s
```

ruff: All checks passed!

### Full suite

```
cd backend && uv run --extra dev pytest -q --basetemp=E:/polymarket-worktrees/loop94-marketplace/.ptf
1 failed, 2038 passed, 28 skipped in 447.74s (0:07:27)
```

Unrelated failure (not marketplace; do not fix per anti-gold-plating):
`tests/test_openapi_snapshot.py::test_openapi_surface_matches_snapshot`
— `GET /api/v1/search` summary/tags drift (`Search Markets`/`public` → `Get Market Search`/`search`).

## AutoLab

AutoLab: not applicable (no iterative measure)

## Commits

```
199f25a feat(loop94): M4 — featured lists + admin feature toggle
1f2b94d feat(loop94): M3 — deterministic skills/scanners trending endpoints
8cc2383 feat(loop94): M2 — skill/scanner rate endpoints with upsert
6cc8ac3 feat(loop94): M1 — marketplace ratings tables + is_featured
```
