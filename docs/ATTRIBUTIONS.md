# AlphaEdge — Third-Party Attributions

This file records source-code attributions per the Loop C §G4 license policy.

## pmxt (MIT)

- **Repo**: https://github.com/pmxt-dev/pmxt
- **License**: MIT
- **Used in**: `backend/app/schemas/market.py` (`UnifiedMarketSearchResult`),
  `backend/app/services/market_service.py` (`search_markets`)
- **What was adapted**: The `UnifiedMarket` dataclass field shape
  (`vendor-study/pmxt-dev__pmxt/sdks/python/pmxt/models.py`) informed the
  fields in `UnifiedMarketSearchResult` (slug, title, platform/source_exchange,
  category, yes_price, volume, status).  No code was copied verbatim; the
  structure was re-implemented in Pydantic against AlphaEdge's DB schema.
- **Ticket**: U01 — Unified market search
