# STATE114 — identifier Text sweep + year-boundary placeholder locks

**Role:** Backend engineer (Cursor Grok 4.5 High), worktree `loop114-slugsweep`
**Branch:** `loop114-slugsweep/node`
**Commits:**
1. `fix(loop114): Text sweep for external identifiers (069)`
2. `fix(loop114): year-boundary placeholder lock detection`

## FIX 1 — identifier sweep (migration 069)

Prod hit `value too long for varchar(128)` twice (venue_market_matches → 068;
wallet_position_snapshots.market_slug → live whale boot catch-up crash).
Swept every remaining open-ended identifier `String(N<=256)` in models.py to
`Text`. Enum/status/short-code columns left alone. venue match/gap slugs
already TEXT in 068 — not re-listed.

### Swept columns (`backend/app/db/models.py`:line)

| Line | Class.column | Was |
|------|--------------|-----|
| 117 | PaperOrder.slug | String(128) |
| 162 | Watchlist.slug | String(128) |
| 261 | MarketResolution.slug | String(128) |
| 347 | Market.slug | String(128) |
| 359 | Market.external_slug | String(256) |
| 360 | Market.external_id | String(128) |
| 361 | Market.clob_token_id | String(128) |
| 516 | OddsSnapshot.market_slug | String(128) |
| 521 | OddsSnapshot.event_id | String(128) |
| 522 | OddsSnapshot.platform_market_id | String(128) |
| 536 | FeatureSnapshot.market_slug | String(128) |
| 617 | PredictionLog.market_slug | String(128) |
| 683 | SignalEvent.market_id | String(128) |
| 746 | TrackedWallet.wallet_address | String(64) |
| 773 | WalletPosition.market_id | String(128) |
| 807 | WalletPositionSnapshot.wallet_address | String(64) |
| 808 | WalletPositionSnapshot.market_slug | String(128) |
| 832 | WhaleEvent.wallet | String(64) |
| 838 | WhaleEvent.market_slug | String(128) |
| 839 | WhaleEvent.market_id | String(128) |
| 840 | WhaleEvent.tx_hash | String(128) |
| 861 | MarketSentimentSnapshot.market_slug | String(128) |
| 913 | AnalystBrief.market_slug | String(128) |
| 914 | AnalystBrief.trigger_event_id | String(64) |
| 945 | BriefClaim.market_slug | String(128) |
| 1020 | ResearchSession.market_slug | String(128) |
| 1280 | ExternalMarket.external_id | String(128) |
| 1456 | AgentCloneRun.market_slug | String(128) |
| 1620 | BacktestRun.market_slug | String(128) |
| 1662 | AgentMemory.market_slug | String(128) |
| 1719 | HeartbeatDecisionLog.position_ref | String(256) |

**Excluded (judgment):** enum-like status/side/outcome/action/source/category;
hashes; display names; titles; URLs; internal `BacktestRun.clone_id`.

**Migration:** `backend/alembic/versions/069_ident_text.py` chains on
`068_sluglen_text`; per-table short txns + lock_timeout + information_schema
idempotency (067/068 pattern). Downgrade: `VARCHAR(128) USING left(col,128)`.

**Parity harness:** `tests/test_migration_exercise.py` not run — no
`TEST_MIGRATION_DATABASE_URL` scratch DSN in this environment. Model +
migration agree on TEXT for the 31 columns; re-run where scratch Postgres exists.

## FIX 2 — placeholder lock detector

VERIFY112: prod Israel-PM locks `2026-12-31T00:00Z` / `2045-01-01T15:00Z`
were treated as sharp → `resolution_date_reject` → confidence 0.

`_is_placeholder_end` widened minimally: Dec 30–Jan 2 **and** whole hour
(minute==0, second==0). Classic Polymarket Dec 31 23:59 kept. Mid-season
game locks stay sharp. No other matcher thresholds / PAPER flags / order path.

## Guardrails

PAPER_TRADING_ONLY untouched. No order-path / LLM. No secrets printed.
No push/deploy. Explicit `git add` only (no `git add -A`).

## AutoLab

AutoLab: not applicable (no iterative measure) — one-shot schema + detector widen.

## STOP proof (verbatim)

### targeted pytest (both new files + tests/test_loop112_matcher.py + tests/test_loop113_sluglen.py)

```text
..............................                                           [100%]
30 passed in 35.01s
```

### ruff

```text
All checks passed!
```

### alembic heads (single 069)

```text
069_ident_text (head)
```

### full suite summary

```text
2203 passed, 30 skipped in 422.04s (0:07:02)
```
