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
