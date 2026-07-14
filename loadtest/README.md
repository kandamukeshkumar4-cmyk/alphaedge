# Loop V20 — Local Load & Performance Baseline

**LOCAL STACK ONLY.** Never aim these tools at Railway, Vercel, Hugging Face,
or any non-loopback host. Scenarios refuse non-local hosts.

## Ownership

- `loadtest/**` — this harness
- `goals/loop-v20-load/**` — loop state
- Findings that need app code changes → **PERF REPORTS** in `STATE.md` (do not edit `backend/**` or `frontend/**` here)

## Quick start

```powershell
# From repo root (worktree loop20-load)
# L1 smoke: boot isolated SQLite + uvicorn, 20 VUs × 60s on /health + /markets
py -3.13 loadtest/scripts/run_smoke.py

# Boot stack alone (stays up until Ctrl+C)
py -3.13 loadtest/scripts/boot_local_stack.py --port 18020

# Stack health check only
py -3.13 loadtest/scripts/boot_local_stack.py --check
```

Default API port: **18020** (`LOADTEST_API_PORT`). Host: `http://127.0.0.1:18020`.

## Layout

| Path | Role |
|------|------|
| `scripts/boot_local_stack.py` | Isolated SQLite + uvicorn (A6/E5 / V17 pattern) |
| `scripts/init_sqlite_db.py` | Schema create_all for the load DB |
| `scripts/run_smoke.py` | L1: 20 VU / 60s |
| `scripts/run_read_path.py` | L2: read-path baseline |
| `scripts/run_trade_path.py` | L3: paper buy/close + 429 onset |
| `scripts/run_all.py` | L4: one-command full baseline |
| `scenarios/*.py` | Locust user classes |
| `results/` | CSV + markdown evidence |

## Guardrails

- `PAPER_TRADING_ONLY=true`
- Mutating rate limits left **enabled** (default 600/min) — L3 documents 429 onset
- Per-scenario wall clock bound &lt; 10 minutes
- Locust installed via `uv run --with locust` (no backend `pyproject` edits)
