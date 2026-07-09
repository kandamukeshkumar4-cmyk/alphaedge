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

## Cross-platform arb repos (no license — ideas only, §G4)

- **Repos**: taetaehoho/arb, ImMike/polymarket-arbitrage, AlexM800/arb-bot,
  TopTrenDev/arb
- **License**: No license declared (§G4: prefer reimplement over paste)
- **Used in**: `backend/app/signals/matching.py` (title-token Jaccard sub-score),
  `backend/app/signals/arb_service.py`, `backend/app/api/v1/arb.py`
- **What was studied**: README-level concept only — the central insight from
  each repo is that "matching the same underlying event across Polymarket
  (free-text titles) and Kalshi (structured event paths) is the hard part".
  No source code was read, cloned, or copied; all logic in matching.py and
  arb_service.py is a clean-room reimplementation.
- **Ticket**: U11 — Cross-platform arb hardening

## Jon-Becker/prediction-market-analysis (MIT)

- **Repo**: https://github.com/Jon-Becker/prediction-market-analysis
- **License**: MIT
- **Used in**: `backend/app/backtesting/snapshot_replay.py`
- **What was adapted**: The conceptual pattern of replaying over a dated price
  series to produce an equity curve (§G4: "Jon-Becker MIT is adaptable for data
  handling with attribution"). No code was copied verbatim; the replay engine is
  an original implementation using AlphaEdge's OddsSnapshot store with the
  no-lookahead enforcement from T08's ClaimScorerService pattern and a bespoke
  realistic fill model in `fill_model.py`.
- **Ticket**: U10 — Backtest replay + realistic fills

## PolyMarket-MCP / polymarket-mcp / polymarket-agents (MIT / ideas)

- **Repos**: guangxiangdebizi/PolyMarket-MCP (MIT), berlinbra/polymarket-mcp,
  artvandelay/polymarket-agents
- **License**: MIT where declared; README/tool-name study only otherwise
- **Used in**: `backend/app/agents/tools.py`
- **What was adapted (Loop 8)**: Clean-room read-only tools inspired by MCP
  surfaces — `get_depth_skew` (order-book imbalance), `get_whale_concentration`
  (holders top-share), `get_trade_intensity` (recent fill rate). No vendor
  source pasted; all use AlphaEdge CLOB/snapshots/fills. Existing
  `get_order_book_summary` / `get_price_history` / `get_whale_activity` remain.
- **Ticket**: Loop 8 L8-T4 — vendor-study MCP gap-fill
