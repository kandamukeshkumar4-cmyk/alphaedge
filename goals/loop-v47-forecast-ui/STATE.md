# loop-v47-forecast-ui — STATE

## Status
| Ticket | Status | Notes |
|--------|--------|-------|
| F1 | **DONE** | `GET /api/v1/markets/{slug}/locked-forecast` matches documented shape |
| F2 | **DONE** | Detail panel: lock %, relative time, vs market + delta, pre-lock, PROVISIONAL |
| F3 | **DONE** | Track-record surfaces `forecast_scored_count` + `source` |

## F1 — endpoint confirmation (2026-07-16, post loop48 merge)

Merged `loop48/unblock`. Read `backend/app/api/v1/market_locked_forecast.py` +
`LockedForecastResponse` in `backend/app/schemas/market.py`.

| Field | Locked | Pre-lock |
|-------|--------|---------|
| `slug` | request slug | request slug |
| `locked` | `true` | `false` |
| `user_probability` | LIVE `ForecastLog.user_probability` | `null` |
| `locked_at` | ISO datetime | `null` |
| `market_implied_at_lock` | float \| null | `null` |
| `current_market_probability` | latest odds \| null | latest odds \| null |
| `mode` | `"live"` | `null` |
| `provisional` | from snapshot meta (default true) | `true` |
| `paper_trading_only` | settings | settings |
| `forecast_id` / `external_market_id` | UUIDs | null / optional |
| `empty_reason` | `null` | `"pre_lock"` |

Backend never invents `%` — empty when no LIVE row. Prefer autolock
forecaster. **Not** `MarketDetailForecast.model_prob` / XGBoost.

## F2 — detail panel

- `frontend/src/lib/locked-forecast-api.ts` — fetch + pure view-model
- `frontend/src/components/LockedForecastPanel.tsx` — panel on market detail
- Locked copy: `Model: locked X% on <relative> · market now Y%` + pts delta
- Pre-lock: **"Model forecast locks near close"**
- PROVISIONAL disclaimer when `provisional`
- Tokens (`border-border`, `bg-surface`, `text-gold`, `text-accent`) — both themes

## F3 — done (prior)

Resolved-count disclosure on `/track-record` (unchanged this pass).

## Adversarial self-review (fresh, F1-F2)

1. **Fabrication?** No — view-model nulls lock % unless `locked && user_probability`;
   API miss → unavailable copy, never mock/XGBoost %.
2. **Wrong source?** Panel calls `/locked-forecast` only; does not use detail
   `forecast.model_prob` for the lock chip.
3. **Empty honesty?** Pre-lock + unavailable both explicit; no invented number.
4. **Theme?** Design tokens only — dark/light inherit.
5. **Scope?** Frontend + STATE only for F1/F2 impl; backend from merge only
   (no backend edits this pass). No deploy/push/merge.
6. **Visreg?** Detail page code changed; `--update-snapshots` wrote no PNG
   diffs (panel below 720/812 fold). 2× consecutive visreg green after.

## LOOP LOG
| loop | date | result | proof |
|------|------|--------|-------|
| 1 | 2026-07-16 | F1 BLOCKED-ON-BACKEND; F2 BLOCKED; F3 DONE | see prior VERIFICATION |
| 2 | 2026-07-16 | F1+F2 DONE (merged loop48); F3 already DONE | see VERIFICATION below |

## VERIFICATION

```text
CHECK COUNTS (vitest): Test Files 69 passed (69) | Tests 398 passed (398)
  (was 67 / 389 — +2 files, +9 tests for locked-forecast)
lint: npm run lint → exit 0
typecheck: npm run typecheck → exit 0
build: npm run build → exit 0
playwright FULL: 53 passed, 1 skipped (5.0m) — visreg 24/24 ok
visreg regen: --update-snapshots → 24 passed; PNG diffs empty (below fold)
visreg ×2 consecutive: 24 passed (2.2m); 24 passed (~2.1m)
gate: py -3.13 orchestration/gate.py --frontend-only → PASS: all checks green
```

AutoLab: not applicable (no iterative measure — F1 confirm + F2 one-shot UI)

### ORCHESTRATOR REVIEW · F1-F2 · pending commit · verdict: PASS (self)
F1 unblocked by loop48 shape match. F2 ships lock chip without fabricating.
F3 already DONE. Stop — F1-F2 complete; do not push/merge.
