# Loop V3 — Backend API notes

Frontend track (loop-opus-polish) integrates from this file. **Additive only** —
never change or remove an existing response shape. All surfaces here are
ANALYSIS ONLY (`signal_only` / `paper_trading_only` true); no order path.

## H01 — `GET /api/v1/desk?slug=` (2026-07-10)

Single-market desk aggregate. Composes, in ONE response, the market snapshot +
latest model-vs-market edge + G07 smart-money summary + G02 arb match (if any) +
latest signal events for the slug, so the market page's intelligence panel
renders with a single call (cuts request flooding). Read-only composition of
EXISTING services (`MarketService`, `OrderBookService` read-only L2,
`build_smart_money_summary` [G07], `VenueMatchService` [G02], `SignalEvent`).
No new pipelines, no new tables.

Query params:

| param | type | default | notes |
|-------|------|---------|-------|
| `slug` | string | required | market slug (local `pm-`/`ks-`/seed slugs) |
| `hours` | int | 24 | smart-money trade-intensity window, 1–168 |
| `top_n` | int | 5 | wallets in the top-holder share, 1–25 |
| `signals_limit` | int | 10 | latest `SignalEvent` rows for the slug, 1–50 |

Unknown slug → **200** with `market_found=false` and honest empties: `market`,
`book`, `edge`, `arb` are `null`; `signals` is `[]`; `smart_money` is present
with its own `market_found=false` zero sections. Never a 404, never fabricated
data.

Response (composed example):

```json
{
  "slug": "pm-will-lakers-beat-celtics",
  "market_found": true,
  "paper_trading_only": true,
  "signal_only": true,
  "disclaimer": "Research desk aggregate — market snapshot, model edge, smart-money and cross-venue observations composed from existing analysis surfaces. Signal only; paper trading only — simulated funds, no execution.",
  "market": { "slug": "pm-will-lakers-beat-celtics", "title": "Will the Lakers beat the Celtics?", "status": "open", "...": "full MarketResponse shape" },
  "book": { "yes": {"bids": [], "asks": []}, "no": {"bids": [], "asks": []} },
  "edge": {
    "predicted_prob": 0.62,
    "confidence": 0.7,
    "edge_vs_book": null,
    "input_feature_hash": "feat-abc",
    "predicted_at": "2026-07-10T17:55:00+00:00",
    "source": "prediction_log"
  },
  "smart_money": {
    "slug": "pm-will-lakers-beat-celtics",
    "hours": 24,
    "market_found": true,
    "paper_trading_only": true,
    "signal_only": true,
    "disclaimer": "Research signal only — aggregated whale/flow observations, not advice. Paper trading only; simulated funds, no execution.",
    "top_holders": {"wallet_count": 1, "top_n": 1, "top_share": 1.0, "total_size": 1500.0, "error": null},
    "recent_large_flows": {"whale_count": 0, "deltas": [], "error": null},
    "depth_skew": {"bid_size": 0.0, "ask_size": 0.0, "skew": 0.0, "levels": 0, "error": null},
    "trade_intensity": {"fill_count": 0, "notional": 0.0, "fills_per_hour": 0.0, "error": null},
    "generated_at": "2026-07-10T18:00:00+00:00"
  },
  "arb": {
    "pm_slug": "pm-will-lakers-beat-celtics",
    "ks_slug": "ks-kxnba-lalbos-26jan15",
    "pm_title": "Lakers beat Celtics",
    "ks_title": "LAL def BOS",
    "confidence": 0.9,
    "reasons": ["title", "date"],
    "stale": false,
    "matched_at": "2026-07-10T18:00:00+00:00",
    "updated_at": "2026-07-10T18:00:00+00:00"
  },
  "signals": [
    {
      "id": "…uuid…",
      "signal_type": "news:mispricing",
      "platform": "polymarket",
      "market_id": "pm-will-lakers-beat-celtics",
      "headline_eligible": true,
      "payload": {"model_p": 0.62, "market_p": 0.5, "gap": 0.12},
      "created_at": "2026-07-10T18:00:00+00:00"
    }
  ],
  "generated_at": "2026-07-10T18:00:00+00:00"
}
```

Notes:
- `edge` is the newest `PredictionLog` for the slug; `edge_vs_book` = model
  probability minus best reference YES price (asks, else bids), null when the
  local book is empty. `null` when no prediction exists.
- `smart_money` is the G07 `GET /api/v1/smart-money` body verbatim (shared
  builder) — the two surfaces can never disagree.
- `arb` is the highest-confidence persisted `VenueMarketMatch` (G02) whose
  `pm_slug` or `ks_slug` equals the requested slug; `null` when none.

## H02 — `GET /api/v1/backtest/summary` (2026-07-10)

Walk-forward Brier + flat-stake ROI over resolved external markets. Read-only,
no params. Computed from the SAME real-resolution source as
`GET /api/v1/track-record` and the G06 resolved-count watcher: scored LIVE
forecasts (`ForecastLog` × `ForecastScore`) on RESOLVED `ExternalMarket` rows.

ROI is a deterministic flat-stake (1-contract) paper strategy consistent with
`app.forecasting.scoring.synthetic_pnl`: bet the model's disagreement with the
market, filled at the market implied price. A forecast within the anchor
epsilon (0.02) of the market, or with no implied price, places NO bet (it still
counts toward Brier). `roi = total_pnl / total_staked`.

| field | type | notes |
|-------|------|-------|
| `n` | int | resolved scored forecasts behind the summary; 0 with no data |
| `thin_data` | bool | `n < thin_data_threshold` — UI must caveat when true |
| `thin_data_threshold` | int | 30 (`BRIER_MIN_SAMPLE`) |
| `brier_score` | float\|null | overall mean user Brier; null when `n == 0` |
| `market_brier_score` | float\|null | mean market Brier over rows with an implied price; null when none |
| `roi` | float\|null | `total_pnl / total_staked`; null when no bet was placed |
| `n_bets` | int | rows that placed a bet (`|edge| ≥ 0.02` and a price exists) |
| `total_pnl` | float | summed flat-stake paper P&L |
| `total_staked` | float | summed cost basis of the bets |
| `walk_forward` | array | per-resolution points ordered by `scored_at`: `{seq, scored_at, brier, cumulative_brier, cumulative_roi}` (`cumulative_roi` null until the first bet) |
| `source` | string | `"forecast_scores"` \| `"none"` |
| `last_updated` | datetime\|null | newest resolution timestamp |
| `paper_trading_only` | bool | always true |
| `signal_only` | bool | always true |
| `disclaimer` | string | research-only wording |

Honest empties: with zero resolutions returns `n=0`, `thin_data=true`,
`source="none"`, null metrics, `walk_forward=[]`. Never fabricates an equity
curve or a resolution.

Example (2 resolutions):

```json
{
  "n": 2,
  "thin_data": true,
  "thin_data_threshold": 30,
  "brier_score": 0.09,
  "market_brier_score": 0.25,
  "roi": 1.0,
  "n_bets": 2,
  "total_pnl": 1.0,
  "total_staked": 1.0,
  "walk_forward": [
    {"seq": 1, "scored_at": "2026-07-10T16:00:00Z", "brier": 0.09, "cumulative_brier": 0.09, "cumulative_roi": 1.0},
    {"seq": 2, "scored_at": "2026-07-10T17:00:00Z", "brier": 0.09, "cumulative_brier": 0.09, "cumulative_roi": 1.0}
  ],
  "source": "forecast_scores",
  "last_updated": "2026-07-10T17:00:00Z",
  "paper_trading_only": true,
  "signal_only": true,
  "disclaimer": "Walk-forward research metrics from REAL resolutions only …"
}
```

## H03 — Signal citation consistency (2026-07-10)

No new HTTP route. Additive payload fields on the two headline-eligible signal
types so F04 can render evidence from either with one shape. Surfaces via the
existing `GET /api/v1/activity/signals/events`, `GET /api/v1/desk` (H01
`signals[]`), and the feed. Persisted `payload` dicts only — no pipeline
change.

Both `news:mispricing` and `anomaly:unusual_flow` payloads now carry the shared
citation contract (`app.signals.news_mispricing.CITATION_FIELDS`):

| field | type | news:mispricing | anomaly:unusual_flow |
|-------|------|-----------------|----------------------|
| `id` | string | stable 16-hex id (`stable_signal_id`) | stable 16-hex id |
| `signal_type` | string | `"news:mispricing"` | `"anomaly:unusual_flow"` |
| `news_id` | string\|null | news item id | `null` (no catalyst) |
| `news_url` | string\|null | news url | `null` |
| `headline` | string | news headline | `""` (or move label) |
| `model_p` | float\|null | model P(YES) | `null` (no model) |
| `market_p` | float\|null | market implied P(YES) | post-move price from `detail.curr`, else `null` |

`id` is a deterministic hash of `(signal_type, market_slug, anchor_ts,
discriminator)` — the news timestamp + news_id for mispricing, the move
timestamp + kind for anomaly — so the same event yields the same id across
scans (stable dedupe / deep-link) and the two types never collide. All other
existing payload fields (G03 `gap`/`threshold`/`news_ts`/`fresh_until`; G04
`kind`/`direction`/`magnitude`/`catalyst`/`note`/`detail`/…) are unchanged.
