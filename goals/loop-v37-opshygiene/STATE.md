# loop-v37-opshygiene — STATE

## LOOP LOG

| loop | date | result | proof |
|------|------|--------|-------|
| H1 | 2026-07-15 | DONE | `aa7f397` per-slug 404 backoff in `live_price_tick.py` (N=3 → lifecycle lock; demoted skip + 1 warn/hr; non-404 never swallowed). tests `test_live_tick_404_backoff.py` |
| H2 | 2026-07-15 | DONE | `f0aa626` `sync_connector_health_gauges()` from C1 registry on `/metrics`; exposition asserts `h2_fred=1` / `h2_onchain=0` |
| H3 | 2026-07-15 | DONE | `4da4be9` `jobrun_retention` dual-wire (main in-process + ARQ cron), flag default on, days=30, batched idempotent delete; `_ALL_LOOPS` + `LOOP_INTERVALS` |
| H4 | 2026-07-15 | DONE | full gate + ruff + fresh verifier PASS (below) |

## SHARED FILE CLAIMS

| file | ticket | status |
|------|--------|--------|
| `backend/app/workers/tasks.py` | H3 | released (additive import + functions/cron only) |
| `backend/app/main.py` | H3 | released (additive `_jobrun_retention_loop` + lifespan flag) |
| `backend/app/core/config.py` | H3 | released (3 settings fields) |
| `backend/app/api/v1/system.py` | H3 | released (`jobrun_retention` in `_ALL_LOOPS`) |

No migration needed (JobRun table + `ix_job_runs_job_started` already exist).

## H4 GATE OUTPUT (pasted)

```text
ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q -p no:cacheprovider
1633 passed, 28 skipped in 330.55s (0:05:30)

uv run --extra dev ruff check app tests
All checks passed!
```

Subset re-check after commits:
```text
14 passed in 8.53s  (H1/H2/H3 focused)
ruff: All checks passed!
```

## ADVERSARIAL VERIFIER

- First seat (read-only, no shell): **FAIL** on H4 unproven (cannot run gate) — not counted as product defect.
- Fresh shell-enabled verifier (`019f6723-4e04-7341-94f7-ed90f5ce9674`): **PASS**
  - Foreign paths absent (`forecast_autolock`, `external_market*`, frontend, deploy)
  - H1 non-404 always warned; N=3 → lifecycle lock
  - H2 gauge sync on `/metrics` scrape
  - H3 dual-wire + heartbeat registration
  - 32 focused tests + ruff green

## Commits (from b811a56)

```
aa7f397 fix(loop37): H1 live-tick per-slug 404 backoff
f0aa626 fix(loop37): H2 wire get_source_health into connector gauge
4da4be9 fix(loop37): H3 JobRun retention dual-wired sweep
```

## AutoLab

AutoLab: not applicable (no iterative measure)

## STOP

H1–H4 DONE. No push/merge.

### ORCHESTRATOR REVIEW · H1-H4 · aa7f397..48b64b9 · verdict: PASS — LOOP V37 COMPLETE
404-backoff discipline verified (non-404 never accumulates), gauges wired,
retention dual-wired + registered. Lane closed.
