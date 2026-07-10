# API notes — Grok backend loop

Frontend loop integrates from this file. **Additive only** — never change or
remove an existing response shape.

## G00 (2026-07-09)

No API changes. Vendor study only (`VENDOR-NOTES.md`).

Full vendor tree (20 clones under `E:\polymarket-vendor\`) documented and
mapped to G01–G07. Still no endpoint deltas.

## G01 (2026-07-09)

No new HTTP endpoints. Internal service seam only:

- Package: `backend/app/services/venues/`
- Protocol: `VenueAdapter` — `fetch_markets`, `fetch_orderbook_summary`,
  `fetch_last_price`, `normalize`
- Registry: `get_venue_adapter("polymarket" | "kalshi")`, `list_venue_ids()`
- Local slug prefixes unchanged: `pm-` / `ks-`

Example (Python, not HTTP):

```python
from app.services.venues import get_venue_adapter

pm = get_venue_adapter("polymarket")
markets = pm.fetch_markets(limit=25)
book = pm.fetch_orderbook_summary("will-lakers-beat-celtics")
# book.yes_bid / yes_ask / mid in [0, 1]
```

Frontend loop: no contract change yet; G02 will add additive arb fields.

## G02 (2026-07-09)

Additive fields on `GET /api/v1/arb/opportunities` (and detect→ingest path).
Existing fields unchanged. Analysis only — `signal_only` always true.

New optional fields per opportunity:

| field | type | notes |
|-------|------|-------|
| `confidence` | float | alias of `match_confidence` |
| `spread_bps` | int | net spread in basis points (`net_spread * 10000`) |
| `legs` | array | `[{platform, market_id, outcome, price, fee}, ...]` |
| `stale` | bool | already existed |

Example opportunity fragment:

```json
{
  "pm_market_id": "pm-will-lakers-beat-celtics",
  "kalshi_market_id": "ks-kxnba-lalbos-26jan15",
  "match_confidence": 0.9,
  "confidence": 0.9,
  "spread_bps": 120,
  "stale": false,
  "signal_only": true,
  "legs": [
    {"platform": "polymarket", "market_id": "pm-will-lakers-beat-celtics", "outcome": "YES", "price": "0.4000", "fee": "0.0000"},
    {"platform": "kalshi", "market_id": "ks-kxnba-lalbos-26jan15", "outcome": "NO", "price": "0.5500", "fee": "0.02"}
  ]
}
```

Internal: matches persist in `venue_market_matches` (pm_slug, ks_slug, confidence,
reasons). Different UTC resolution dates never match.

## G03 (2026-07-09)

New persisted signal type (no new HTTP route — surfaces via existing
`GET /api/v1/activity/signals/events` and feed):

| field | value |
|-------|-------|
| `signal_type` | `news:mispricing` |
| config | `NEWS_MISPRICING_ENABLED=true` (default), threshold `0.05`, window `900s` |
| scheduler | `SCHEDULER_NEWS_MISPRICING_ENABLED=true` (default) |

Example payload:

```json
{
  "signal_type": "news:mispricing",
  "platform": "polymarket",
  "market_id": "pm-will-lakers-beat-celtics",
  "payload": {
    "paper_trading_only": true,
    "model_p": 0.62,
    "market_p": 0.5,
    "gap": 0.12,
    "news_id": "news-lal-injury-1",
    "news_url": "https://example.test/news/lal-injury",
    "headline": "Lakers star ruled out"
  }
}
```

## G04 (2026-07-09)

New persisted signal type (no new HTTP route — surfaces via existing
`GET /api/v1/activity/signals/events` and feed). Inverse of G03: the market
moved but no news item exists in the window. Neutral wording only — "no public
catalyst found" is an observation, never an accusation.

| field | value |
|-------|-------|
| `signal_type` | `anomaly:unusual_flow` |
| config | `ANOMALY_UNUSUAL_FLOW_ENABLED=true` (default), window `900s`, lookback `3600s` |
| scheduler | `SCHEDULER_UNUSUAL_FLOW_ENABLED=true` (default) |
| sources | candidates = diff-engine `delta:price_jump` / `delta:volume_surge` events; news check shared with G03 via `news_in_window` |

Example payload:

```json
{
  "signal_type": "anomaly:unusual_flow",
  "platform": "polymarket",
  "market_id": "pm-will-lakers-beat-celtics",
  "payload": {
    "paper_trading_only": true,
    "kind": "price_jump",
    "direction": "up",
    "magnitude": 0.08,
    "occurred_ts": "2026-07-09T18:00:00+00:00",
    "window_sec": 900.0,
    "catalyst": "none_found",
    "note": "No public catalyst found in the news window.",
    "no_news_reason": "no_news_found",
    "last_news_ts": null,
    "headline": "",
    "detail": {"prev": 0.5, "curr": 0.58, "bps": 800.0}
  }
}
```
