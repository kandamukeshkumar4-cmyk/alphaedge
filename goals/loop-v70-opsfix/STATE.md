# loop-v70-opsfix — STATE

## Status: IN_PROGRESS

## LOOP LOG

| ticket | date | result | proof |
|--------|------|--------|-------|
| setup | 2026-07-17 | STARTED | branch `loop70/ops-fix` |
| F1 | — | pending | retention sweeps for 4 high-growth tables |
| F2 | — | pending | news flag-off 60min per-slug cooldown |
| F3 | — | pending | LOOP_INTERVALS audit vs main.py |
| F4 | — | pending | news heartbeat skipped-reason detail |
| F5 | — | pending | shared CircuitBreaker + TTL cache |
| F6 | — | pending | sentiment_debate client reuse |
| F7 | — | pending | alembic 052/053 docstring revises |

## Out of scope (V74)

- `order_book_service.py`
- `settlement_service.py`
- `admin_markets.py`
- `paper_position_service.py`

## Done when

- One commit per fix: `fix(loop70): <what>`
- Full gate: `py -3.13 orchestration/gate.py --backend-only` (pytest counts + ruff)
- Never push/merge
