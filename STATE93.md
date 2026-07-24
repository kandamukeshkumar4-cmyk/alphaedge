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
