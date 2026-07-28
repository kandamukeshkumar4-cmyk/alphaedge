# Authz matrix classification repair

## Scope and evidence

Only `backend/tests/test_loop26_authz_matrix.py` and this verification report
were changed. No route handler, auth dependency, package manifest, or deploy
configuration was modified.

The OpenAPI snapshot contains 197 paths and 217 operations. The matrix now
covers every operation. The 50 recent operations below were classified by
their actual handler dependencies, then behaviorally checked against anonymous,
JWT-user, and admin-key requests. `heartbeat/decisions` is public because its
admin-key header is optional and only controls response detail; it is not an
admin dependency.

## Endpoint classifications

| Method | Path | Class |
|---|---|---|
| GET | `/api/v1/context/digest` | public |
| GET | `/api/v1/heartbeat/decisions` | public |
| GET | `/api/v1/markets/{slug}/context` | public |
| GET | `/api/v1/markets/{slug}/locked-forecast` | public |
| GET | `/api/v1/notifications/preferences` | user |
| PUT | `/api/v1/notifications/preferences` | user |
| POST | `/api/v1/notifications/push/subscribe` | user |
| GET | `/api/v1/pods` | public |
| GET | `/api/v1/portfolio/analytics` | user |
| GET | `/api/v1/scanners/` | public |
| POST | `/api/v1/scanners/` | user |
| POST | `/api/v1/scanners/compile` | public |
| GET | `/api/v1/scanners/featured` | public |
| GET | `/api/v1/scanners/trending` | public |
| GET | `/api/v1/scanners/{scanner_id}` | public |
| PATCH | `/api/v1/scanners/{scanner_id}` | user |
| POST | `/api/v1/scanners/{scanner_id}/feature` | admin |
| POST | `/api/v1/scanners/{scanner_id}/fork` | user |
| POST | `/api/v1/scanners/{scanner_id}/pause` | user |
| POST | `/api/v1/scanners/{scanner_id}/publish` | user |
| POST | `/api/v1/scanners/{scanner_id}/rate` | user |
| POST | `/api/v1/scanners/{scanner_id}/resume` | user |
| POST | `/api/v1/scanners/{scanner_id}/rollback` | user |
| POST | `/api/v1/scanners/{scanner_id}/run` | user |
| GET | `/api/v1/scanners/{scanner_id}/runs` | public |
| POST | `/api/v1/scanners/{scanner_id}/test-email` | user |
| POST | `/api/v1/scanners/{scanner_id}/test-run` | user |
| GET | `/api/v1/screener` | public |
| GET | `/api/v1/skills/` | public |
| POST | `/api/v1/skills/` | user |
| GET | `/api/v1/skills/featured` | public |
| GET | `/api/v1/skills/trending` | public |
| GET | `/api/v1/skills/{skill_id}` | public |
| POST | `/api/v1/skills/{skill_id}/feature` | admin |
| POST | `/api/v1/skills/{skill_id}/fork` | user |
| POST | `/api/v1/skills/{skill_id}/rate` | user |
| POST | `/api/v1/skills/{skill_id}/run` | user |
| GET | `/api/v1/subscriptions/` | user |
| POST | `/api/v1/subscriptions/` | user |
| DELETE | `/api/v1/subscriptions/{ref_type}/{ref_id}` | user |
| GET | `/api/v1/terminal/sessions` | user |
| POST | `/api/v1/terminal/sessions` | user |
| GET | `/api/v1/terminal/sessions/{session_id}` | user |
| DELETE | `/api/v1/terminal/sessions/{session_id}` | user |
| POST | `/api/v1/terminal/sessions/{session_id}/execute` | user |
| POST | `/api/v1/terminal/sessions/{session_id}/resume` | user |
| POST | `/api/v1/terminal/sessions/{session_id}/save-as-skill` | user |
| GET | `/api/v1/terminal/sessions/{session_id}/stream` | user |
| GET | `/api/v1/usage/summary` | public |
| GET | `/api/v1/venue-gaps` | public |

## Verification

```text
cd backend && uv run --extra dev pytest -q tests/test_loop26_authz_matrix.py --basetemp=E:/polymarket-worktrees/_integration/.ptauthz
..                                                                       [100%]
2 passed in 20.25s
```

```text
cd backend && uv run --extra dev pytest -q --basetemp=E:/polymarket-worktrees/_integration/.ptauthzf
2060 passed, 28 skipped in 368.52s (0:06:08)
```
