# loop-v47-forecast-ui — STATE

## Status
| Ticket | Status | Notes |
|--------|--------|-------|
| F1 | **BLOCKED-ON-BACKEND** | No public GET exposes a market's LIVE `ForecastLog` |
| F2 | **BLOCKED** | Depends on F1 — detail panel would fabricate without API |
| F3 | **DONE** | Track-record surfaces `forecast_scored_count` + `source` |

## F1 — backend audit (2026-07-16)

Searched `backend/app/api/v1/**` for a public per-market LIVE `ForecastLog` read.

| Candidate | Verdict |
|-----------|---------|
| `GET /api/v1/markets/{slug}/detail` → `forecast` | **Not ForecastLog** — `ForecastService.predict()` / XGBoost `model_prob` + CLV gate flags only (`MarketDetailForecast`) |
| `GET /api/v1/markets/{slug}/prediction` | Live predictor, not locked ledger |
| `forecast_routes.py` | `POST /forecasts` (auth), `GET /forecasters/me/dashboard` + `forecast-lifecycle` (auth token) — **no** public by-slug/by-external-id LIVE lock read |
| Aggregates (`/track-record`, `/resolved`, `/calibration`, `/backtest/*`) | Scored LIVE rows only after resolution — not open-market lock chip |

Autolock writes LIVE rows on `ExternalMarket` via system forecaster
(`AUTOLOCK_FORECASTER_ID`); nothing public returns that row for a market slug.

### BLOCKED-ON-BACKEND — exact response shape needed

Public, read-only (no auth, no order path). Prefer either:

**A. Dedicated endpoint (preferred for live PM/Kalshi slugs):**
`GET /api/v1/markets/{slug}/locked-forecast`

**B. Additive field on an existing public detail path** that already serves live
slugs (not catalog-only `/detail` if that stays `CATALOG_SLUGS`-gated).

```json
{
  "slug": "string",
  "locked": true,
  "user_probability": 0.62,
  "locked_at": "2026-07-15T18:00:00+00:00",
  "market_implied_at_lock": 0.55,
  "current_market_probability": 0.58,
  "mode": "live",
  "provisional": true,
  "paper_trading_only": true,
  "forecast_id": "uuid-optional",
  "external_market_id": "uuid-optional",
  "empty_reason": null
}
```

Pre-lock / no LIVE row (honest empty — UI copy: "Model forecast locks near close"):

```json
{
  "slug": "string",
  "locked": false,
  "user_probability": null,
  "locked_at": null,
  "market_implied_at_lock": null,
  "current_market_probability": 0.58,
  "mode": null,
  "provisional": true,
  "paper_trading_only": true,
  "forecast_id": null,
  "external_market_id": null,
  "empty_reason": "pre_lock"
}
```

Rules for backend implementer (out of this worktree's ownership):
- `user_probability` MUST be the LIVE `ForecastLog.user_probability` (autolock /
  system forecaster), never a fresh XGBoost call.
- `null` when unlocked — never invent a %.
- `slug` must resolve the same identity the bridge/autolock funnel uses
  (`ExternalMarket.external_id` / venue slug), including non-catalog live markets.
- Do not confuse with existing `MarketDetailForecast.model_prob`.

## F3 — done

- Extended `ResolvedCountResponse` + `buildResolvedCountDisclosure` in
  `frontend/src/lib/model-ab-api.ts` (tolerant of older APIs missing fields).
- `ResolvedCountDisclosure` on `/track-record` under Forecast reliability.
- Vitest covers scored / fallback / absent-field cases.

## Adversarial self-review (fresh)

1. **Fabrication?** F2 not shipped. F3 only labels API fields; missing → "—" /
   "Source undisclosed", never invents scored count.
2. **Wrong endpoint for F2?** Confirmed detail `forecast` ≠ ForecastLog; using
   it for "locked X%" would be a lie — correctly blocked.
3. **Theme?** Disclosure uses existing tokens (`border-border`, `bg-surface`,
   `text-gold` for fallback warning) — both themes inherit token swaps.
4. **Scope leak?** No `backend/**`, no deploy, no push/merge.
5. **Visreg?** Detail page unchanged (F2 blocked) — no baseline regen.

## LOOP LOG
| loop | date | result | proof |
|------|------|--------|-------|
| 1 | 2026-07-16 | F1 BLOCKED-ON-BACKEND; F2 BLOCKED; F3 DONE | see VERIFICATION below |

## VERIFICATION

```text
vitest: Test Files 67 passed (67) | Tests 389 passed (389)
lint: npm run lint → exit 0
typecheck: npm run typecheck → exit 0
build: npm run build → exit 0
playwright: 53 passed, 1 skipped (7.1m) — visreg 24/24 ok, detail unchanged → no baseline regen
gate: py -3.13 orchestration/gate.py --frontend-only → PASS: all checks green
```

AutoLab: not applicable (no iterative measure — F1/F2 blocked on backend; F3 one-shot disclosure UI)

### ORCHESTRATOR REVIEW · F1-F3 · 102ff42 · verdict: PASS (F3) + BLOCKED accepted (F1/F2)
Correct refusal to fabricate. The requested endpoint shape is queued as a
backend micro-ticket for the first free backend runner (V42 or V46 closer);
this lane resumes on F1/F2 when it lands. Runner: STAND BY (session may
close; the orchestrator will relaunch with the unblock).
