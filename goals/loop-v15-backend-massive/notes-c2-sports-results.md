# C2 — Sports results connector

## Exists (before)

- odds_api (needs ODDS_API_KEY), no sports-results connector, no sports.py
- balldontlie now requires `BALLDONTLIE_API_KEY` (not preferred)

## Added

- `sports_results.py`: ESPN public NBA scoreboard via `JsonConnectorClient` (source=`espn-nba`, no key)
- Pure normalize + `games_to_signal_events` → `sports:result` SignalEvents with `resolves_markets=False`
- `sports.py`: GET `/api/v1/sports/results`, POST `/api/v1/sports/ingest` (deduped SignalEvent persist)
- Fixture/MockTransport tests only

## Guardrails

- Does NOT resolve/settle markets (external_resolve / loop-v14 territory)
- PAPER_TRADING_ONLY / order path untouched
