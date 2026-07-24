# V93 Technical Analysis — Backend

## Charter

- Owned: `backend/app/services/technical_analysis_service.py`,
  `backend/app/api/v1/indicators.py`, `backend/tests/test_technical_analysis.py`,
  and this file.
- No migrations and no order-path changes. Candle data is read through the
  existing `market_candles._build_market_candles` helper.
- The merge orchestrator, not this node, must wire `indicators.router` into
  `backend/app/main.py`.

## T1 — indicator calculations

Status: DONE

Implemented deterministic RSI(14), MACD(12/26/9), SMA(20/50), EMA(12),
Bollinger(20,2), and ADX(14). Missing data produces null indicator values;
missing highs/lows are derived from close.

Proof:

```text
cd backend && uv run --extra dev pytest -q tests/test_technical_analysis.py --basetemp=E:/polymarket-worktrees/loop93-ta/.pt
...                                                                      [100%]
3 passed in 38.71s

cd backend && uv run --extra dev ruff check app tests
All checks passed!

git log -1 --oneline
499aa65 feat(loop93): T1 — technical analysis indicators
```

## T2 — regime classifier

Status: DONE

Added the frozen deterministic classifier: ADX at or below 20 is `range`; a
stronger trend uses SMA(20) versus SMA(50); absent long-trend inputs return
`insufficient_data`.

Proof:

```text
cd backend && uv run --extra dev pytest -q tests/test_technical_analysis.py --basetemp=E:/polymarket-worktrees/loop93-ta/.pt
.......                                                                  [100%]
7 passed in 7.98s

cd backend && uv run --extra dev ruff check app tests
All checks passed!

git log -1 --oneline
ddfb425 feat(loop93): T2 — classify technical regimes
```

## T3 — public indicators endpoint

Status: DONE

Created `GET /api/v1/markets/{slug}/indicators?window=90`. It is public and
read-only, uses the existing `_build_market_candles` helper, preserves the
frozen JSON contract, returns 400 for windows outside 20–365, and forwards the
existing market-not-found 404. `main.py` was intentionally not changed; the
merge orchestrator must include `indicators.router`.

Proof:

```text
cd backend && uv run --extra dev pytest -q tests/test_technical_analysis.py --basetemp=E:/polymarket-worktrees/loop93-ta/.pt
...........                                                              [100%]
11 passed in 7.27s

cd backend && uv run --extra dev ruff check app tests
All checks passed!

git log -1 --oneline
9c4464a feat(loop93): T3 — expose market indicators
```
