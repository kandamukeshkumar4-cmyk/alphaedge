# Triage: "20 free GitHub repos for Polymarket trading" (2026-07-04)

Rule applied: repos are **technique references, never vendored code** (AGENTS.md).
Nothing that auto-executes, touches wallets, or bypasses RiskService→OrderIntent
is ever adopted. The source article itself warns of drainer repos — no repo was
cloned or executed; ideas were adopted clean-room where valuable.

## Already built in earlier loops (no action)
| Repo idea | Our equivalent |
|---|---|
| polybot (trader pattern analysis) | `signals/smart_money.py` whale qualification + tracker |
| collectmarkets2 (wallet history/stats) | `wallet_service` + `trader_profile_service` |
| pmxt (cross-platform market search) | unified Kalshi+Polymarket catalog + `/markets` API |
| Composio arb bot (PM↔Kalshi arb) | `signals/arb_service.py` + resolution matching + `/api/v1/arb` (detection only) |
| polymarket_lp_tool / HarrierOnChain toolkit | REJECTED core (auto-execution) — whale-alert idea already in alert_dispatch |
| MrFadiAi copy-trading | REJECTED (auto copy-trading violates order-path guardrail); leaderboard analysis exists in clone_leaderboard_service |
| evan-kolberg backtesting | backtest API + T08 no-lookahead eval harness |
| TradingAgents (multi-angle AI) | analyst personas (macro/whale-flow/news) over one pipeline |
| polymarket-mcp-server | REJECTED ("let it trade for you" = banned); read-only analysis already native |
| last30days-skill | already integrated (news_signal pipeline) |
| pydantic-ai / gpt-researcher | agent graph + research_digest_service cover the use case |

## Built THIS session (clean-room, ideas only)
- **Weather edge desk** (hermes_weatherbot Gaussian bucket + suislanchez GFS
  pricing + MoonsatProtocol NWS-vs-price + PolyWeather multi-source idea):
  `signals/weather_model.py` + `services/weather_desk.py` +
  `GET /api/v1/weather/edges`. Free NWS forecasts vs live Kalshi daily-high
  ladders, 7 cities, informational edges only. Live-verified.
- Kelly sizing (MoonsatProtocol) — already existed (`risk/rules.py` fractional Kelly).

## Queued (worth a future ticket)
- **Forecast-error learning** (AruneshDev): store forecast vs NWS-settled actual
  per city/source; learn per-city bias + empirical sigma to replace the 2.0F
  default. Needs weeks of accumulated rows first — start logging now.
- **CloddsBot strategy screeners** (MIT-check first): deterministic expiry-fade
  and momentum *screeners* (signals only, no execution) over odds_snapshots.
- **SII-WANGZJ 107GB dataset**: offline calibration source for the LightGBM A/B
  (E06) — needs a download/storage decision from the owner.

## Rejected outright
Anything requiring wallet keys, live order placement, or copy-trade execution
(CloddsBot execution layer, LP reward bot, copy-trading bots, MCP auto-trade).
Reason: PAPER_TRADING_ONLY + LLM-cannot-submit-orders are non-negotiable.
