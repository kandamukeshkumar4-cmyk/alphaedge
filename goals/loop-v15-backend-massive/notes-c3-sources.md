# C3 — Source health endpoint

## Exists (before)

- C1 `get_source_health()` / `SourceHealth` registry
- Public `GET /api/v1/system/loops` + `/metrics` (no connector health)
- Admin gate: `verify_admin_api_key` + `X-Admin-API-Key`

## Added

- `refresh_source_health()` in `http.py` (lazy cooldown expire)
- Admin-gated `GET /api/v1/system/sources` via `sources_router` in `sports.py`
- Reports state, successes/failures, last_error, ages — no fabricated counters
- Fixture tests: missing/wrong key, healthy+open rows, empty registry
