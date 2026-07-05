# Plan 006: Seed OddsSnapshot on live market ingest

> **Executor instructions**: Follow step by step. Run every verification command.
> If STOP conditions occur, stop and report. Update `plans/README.md` when done.
>
> **Drift check**: `git diff --stat 24fa35f..HEAD -- backend/app/services/live_market_ingest.py backend/app/services/kalshi_live_ingest.py backend/tests/`

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/005-kalshi-live-api-parity.md (DONE)
- **Category**: bug
- **Planned at**: commit `24fa35f`, 2026-06-12

## Why this matters

Live ingest upserts `Market` rows but does not write an initial `OddsSnapshot`. Until the first worker tick (~15s), `yes_price` is null and the frontend falls back to hash-seeded fake prices. Seeding on import gives correct first paint on home hero and match cards.

## Current state

- `backend/app/services/live_market_ingest.py` `_upsert_market` (L129–175): creates/updates market only; Gamma payload has `outcomePrices` JSON in tests (`test_live_markets.py` L32–33)
- `backend/app/services/kalshi_live_ingest.py` `_upsert_market` (L107–157): same; Kalshi market dict has price fields via connector (`yes_bid`, `last_price`, etc. — verify in `app/data/connectors/kalshi.py` `normalize_kalshi_market`)
- Worker already writes snapshots in `price_feed_worker.py` `run_live_tick_once` (L144–158)

## Commands you will need

| Purpose | Command | Expected |
|---------|---------|----------|
| Live market tests | `cd backend && uv run --extra dev pytest -q tests/test_live_markets.py tests/test_kalshi_live_ingest.py` | all pass |
| Lint | `cd backend && uv run --extra dev ruff check app tests` | exit 0 |

## Scope

**In scope**
- `backend/app/services/live_market_ingest.py`
- `backend/app/services/kalshi_live_ingest.py`
- `backend/tests/test_live_markets.py` (extend)
- `backend/tests/test_kalshi_live_ingest.py` (extend)

**Out of scope**
- Worker tick loop, frontend, deploy scripts, `hf_stage/`

## Steps

### Step 1: Add shared helper `seed_initial_snapshot`

Create `backend/app/services/live_snapshot_seed.py` with:

```python
async def seed_initial_snapshot_if_missing(
    session: AsyncSession,
    *,
    slug: str,
    implied_yes: float,
    source: str,
) -> None:
```

- Query latest `OddsSnapshot` for `slug`; if any row exists, return (do not duplicate).
- Clamp `implied_yes` to `[0.01, 0.99]`.
- Insert one `OddsSnapshot` with `captured_at=now(UTC)`, `source=f"{source}-seed"`.

### Step 2: Polymarket ingest

In `_upsert_market`, after add/update:
- Parse yes price from `outcomePrices` (first element) using same logic as `PolymarketGammaConnector` / `probability_from_decimalish`.
- Call `seed_initial_snapshot_if_missing` when price is valid.

### Step 3: Kalshi ingest

In `_upsert_market`, after add/update:
- Parse yes from payload: prefer `yes_ask` / `last_price` / midpoint — match `normalize_kalshi_market` field priority.
- Call helper with `source="kalshi.rest"`.

### Step 4: Tests

- Polymarket: after ingest fake market, assert one `OddsSnapshot` with expected `implied_yes`.
- Kalshi: unit test with minimal market dict + assert snapshot seeded (mock session or use existing db_session fixture pattern from `test_live_markets.py`).

**Verify**: `pytest -q tests/test_live_markets.py tests/test_kalshi_live_ingest.py` → all pass

## STOP conditions

- Ingest would write duplicate snapshots on every re-import (must only seed when missing)
- Price parsing requires network
- `PAPER_TRADING_ONLY` weakened

## Done criteria

- [x] New markets get one `OddsSnapshot` on first ingest
- [x] Re-ingest does not duplicate snapshots
- [x] pytest + ruff pass
- [x] `plans/README.md` row 006 → DONE

## Maintenance notes

- If ingest interval writes prices every run, keep "only if missing" guard or switch to upsert-latest pattern in a follow-up.
