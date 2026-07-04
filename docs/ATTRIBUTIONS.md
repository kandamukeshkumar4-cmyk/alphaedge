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

## TradingAgents (Apache-2.0)

- **Repo**: https://github.com/TauricResearch/TradingAgents
- **License**: Apache-2.0
- **Used in**: `backend/app/agents/clone_service.py`
- **What was adapted**: Orchestration patterns for multi-agent graph composition
  studied for the clone config structure (how to select a subset of nodes with
  typed params). No code was copied verbatim; the clone service is an original
  implementation building on AlphaEdge's existing `GRAPH_NODES` / `run_agent_graph_with_trace`.
- **Ticket**: U06 — Agent Builder (Clone-lite)
