# Loop V58 — Master data pipeline: whales + cross-venue + news/sentiment

Reference repos (READ ONLY, E:/polymarket-reference/): polymarket-whales,
polyterm, polymarket-whale-watcher, DeepEar, browser-use. Extract techniques,
never vendor wholesale, cite adapted designs.

## Outcome
A continuously-refreshed "master context" the prediction/pods layer can read:
whale flow, cross-venue price gaps, and news/sentiment per market keyword —
persisted in DB tables AND exposed via API. Every minute for prices/whales
(bounded), coarser for news. No browser automation in prod — public APIs only
(Polymarket data-api for large trades/holders, Kalshi public API, existing
news_signal/last30days pipeline for news).

## Hard constraints
- Read-only external calls; polite rate limits + circuit breakers; no API
  keys beyond existing ones; no scraping that violates ToS.
- No order-path changes; analysis-only outputs. Leakage gate: everything
  timestamped at capture; consumers must filter to pre-close.
- In-process flag-gated loops (_ALL_LOOPS pattern), migration 050+ (<=32
  chars), coordinate: V57 takes 049.

## Tickets (one commit each, feat(loop58): <ticket>)
- D1 Whale flow: `app/signals/whale_flow.py` + worker loop — poll Polymarket
  data-api for large trades on our tracked external markets; store
  whale_events (migration 050_whale_flow: wallet, side, size, price, market,
  captured_at); derive per-market whale_pressure in [-1,1].
- D2 Cross-venue gap: for markets present on both venues (kalshi ks- and
  polymarket pm- via existing matching/arb modules) compute and store implied
  probability gaps + staleness; surface top gaps via API.
- D3 Master context: `GET /api/v1/markets/{slug}/context` — composes whale
  pressure, venue gap, news signal, price trend, volume percentile into one
  timestamped JSON (the "master file" from the reference architecture, but
  queryable); plus `GET /api/v1/context/digest` for the fleet.
- D4 Wire whale_pressure + venue_gap as bounded features into the prediction
  graph beside news/nemotron nodes (flag WHALE_SIGNAL_ENABLED default false).
- D5 Tests (mocked externals, rate-limit respected, leakage timestamps,
  context endpoint shape) + full gate (CHECK COUNTS; ruff). STATE.md.

Stop when D1-D5 DONE or BLOCKED in goals/loop-v58-data-pipeline/STATE.md.
Never push/merge.
