# Plan 005: Kalshi live-mirror API parity (candles + latest price)

> **Executor instructions**: Follow step by step. Run every verification command.
> If STOP conditions occur, stop and report. Update `plans/README.md` status when done.
>
> **Drift check**: `git diff --stat 24fa35f..HEAD -- backend/app/api/v1/market_candles.py backend/tests/`

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `24fa35f`, 2026-06-12

## Why this matters

Frontend hero/grid treats Kalshi (`source=kalshi`, `ks-kxwcgame-*`) as live mirror markets and calls `/candles` and `/prices/latest`. Backend gates those endpoints to `source == "polymarket"` only, so Kalshi slugs 404 or fall back to synthetic candles. Fixing this unblocks real charts on match cards without UI hacks.

## Current state

- `backend/app/api/v1/market_candles.py` L30–33: 404 unless catalog slug OR `market.source == "polymarket"`
- L33: `is_live = market.source == "polymarket"` — Kalshi ticks stored in `OddsSnapshot` are ignored for live candle path
- `get_latest_price` L74–77: same polymarket-only gate for non-catalog slugs
- Polymarket live tests exist in `backend/tests/test_live_markets.py`; Kalshi only has slug test in `test_kalshi_live_ingest.py`

## Commands you will need

| Purpose | Command | Expected |
|---------|---------|----------|
| Backend tests | `cd backend && uv run --extra dev pytest -q tests/test_kalshi_live_api.py tests/test_live_markets.py` | all pass |
| Lint | `cd backend && uv run --extra dev ruff check app tests` | exit 0 |

## Scope

**In scope**
- `backend/app/api/v1/market_candles.py`
- `backend/tests/test_kalshi_live_api.py` (new)

**Out of scope**
- WS multiplex, ingest seeding, frontend changes, hf_stage/

## Implementation steps

### 1. Add helper for live mirror sources

In `market_candles.py`, define:

```python
_LIVE_MIRROR_SOURCES = frozenset({"polymarket", "kalshi"})

def _is_live_mirror(market) -> bool:
    return market.source in _LIVE_MIRROR_SOURCES
```

### 2. Fix `get_market_candles`

- Line ~30: allow market when `slug in CATALOG_SLUGS` OR `market.source in _LIVE_MIRROR_SOURCES`
- Line ~33: `is_live = _is_live_mirror(market)`
- Keep live path: no synthetic candles when `is_live` (only `bucket_snapshots` from `OddsSnapshot`)

### 3. Fix `get_latest_price`

- Line ~74–77: for non-catalog slugs, allow `market.source in _LIVE_MIRROR_SOURCES` (not only polymarket)

### 4. Add tests `backend/tests/test_kalshi_live_api.py`

Use existing async test patterns from `test_live_markets.py`:
- Insert a Kalshi market row (`source="kalshi"`, slug `ks-kxwcgame-test-can`)
- Insert one `OddsSnapshot` with `implied_yes=0.54`
- GET `/api/v1/markets/{slug}/candles?points=10` → 200, `source=="live"`, candles non-empty
- GET `/api/v1/markets/{slug}/prices/latest` → 200, `yes==0.54`, `source=="db"`
- Negative: unknown slug → 404

## STOP conditions

- `PAPER_TRADING_ONLY` guard weakened
- Catalog Lakers market candle behavior regresses (run one catalog slug test if unsure)
- Tests require network calls to Kalshi/Polymarket

## Done criteria

- [ ] Kalshi slugs return 200 on candles + latest price when market exists in DB
- [ ] `pytest -q tests/test_kalshi_live_api.py` passes
- [ ] `ruff check app tests` passes
- [ ] `plans/README.md` row 005 marked DONE
