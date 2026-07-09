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
