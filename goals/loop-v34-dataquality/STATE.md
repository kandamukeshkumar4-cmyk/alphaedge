# loop-v34-dataquality — STATE

## SHARED FILE CLAIMS
| file | workstream | ticket | status |
|------|------------|--------|--------|
| `backend/app/api/v1/activity.py` | loop34 | D2 | RELEASED (title fallback only) |
| `backend/app/workers/tasks.py` | loop34 | D2 | RELEASED (weather rekey append only) |
| `backend/app/data/connectors/polymarket.py` | loop34 | D2 | RELEASED (event-title enrich only) |

## LOOP LOG

| ticket | date | result | proof |
|--------|------|--------|-------|
| D1 | 2026-07-15 | DONE | prod API audit tables below |
| D2 | 2026-07-15 | DONE | code repair + fixture tests |
| D3 | 2026-07-15 | DONE | 1620 passed, ruff clean, verifier |

---

## D1 — Read-only audit (prod API + local logic)

**Source:** `GET https://alphaedge-api-production-b9db.up.railway.app/api/v1/markets`
(full catalog, 2026-07-15T17:39Z) + `GET .../signals/events?limit=200` + category
summaries. Local code reviewed: Kalshi title-fold, V16 V5 `lapse_expired_markets`,
`LivePriceTickService`, `categorize`, `weather_scan_to_events`.

**Catalog snapshot:** 722 markets — open=378, locked=198, resolved=146.
Sources: polymarket=676, kalshi=24, seed=22.

### 1) Duplicate market titles / slug families

| metric | count | notes |
|--------|------:|-------|
| Exact duplicate title groups | 1 | 2 markets share one title |
| Markets in exact-title dups | 2 | different match fixtures |
| OPEN identical-title groups | **0** | Kalshi outcome fold working on prod |
| Multi-member slug families | 49 | 209 markets — mostly legitimate multi-outcome series |

**Examples (duplicate title):**

| title | slugs | status |
|-------|-------|--------|
| `Kylian Mbappé: 1+ goals` | `pm-fifwc-fra-mar-2026-07-09-goals-kylian-mbappe-gte1` | locked |
| same | `pm-fifwc-fra-esp-2026-07-14-goals-kylian-mbappe-gte1` | resolved |

Root cause: PM prop `question` omits parent event; ingest wrote raw question as title.

### 2) Stale open markets past close_at / lock_at

| metric | count |
|--------|------:|
| OPEN with `lock_at` < now | **0** |
| OPEN with null `lock_at` | 0 |
| OPEN extreme price (≤1¢ or ≥99¢) | 186 |

`lapse_expired_markets` effective for past `lock_at`. Gap: Kalshi board absence
was `missing-upstream` without lock.

### 3) Category miscounts

| category (DB raw) | total | open |
|-------------------|------:|-----:|
| Sports | 201 | 62 |
| Crypto | 132 | 49 |
| Politics | 103 | 90 |
| Culture | 83 | 27 |
| Tech | 72 | 52 |
| Economics | 64 | 49 |
| NBA | 56 | 44 |
| FIFA WC2026 | 6 | 0 |
| Elections | 2 | 2 |
| Weather | 2 | 2 |
| NFL | 1 | 1 |

| summary endpoint | market_count |
|------------------|-------------:|
| sports | 264 |
| politics | 105 |
| crypto | 132 |

**Mis-taxonomy examples:** Trump WC final → Sports (should Politics);
155 FIFA-ish markets as Sports vs 6 FIFA WC2026; Kalshi climate→Tech.

### 4) Orphan signal_events

| metric | count |
|--------|------:|
| Sample size | 200 |
| Orphan (`market_title` null) | **19 (9.5%)** |
| Unique orphan market_ids | 12 |
| Platform | kalshi `delta:weather_edge` |

Examples: `KXHIGHMIA-26JUL16-B96.5` (×3), `KXHIGHLAX-26JUL16-B85.5` (×2), …

Root cause: raw ticker as `market_id` vs local `ks-{ticker.lower()}`.

---

## D2 — Repair (code, idempotent)

| issue | fix | files |
|-------|-----|-------|
| Title collisions | `fold_display_title` + event `_event_title` from Gamma events list | `hygiene.py`, `polymarket.py`, `live_market_ingest.py` |
| missing-upstream OPEN | lock via `_apply_terminal_state(..., outcome=None)` — **no resolve** | `live_price_tick.py` |
| Categories | politics before WC; WC→FIFA WC2026; climate→Weather | `live_market_ingest.py`, `kalshi_live_ingest.py` |
| Orphan signals | `canonical_kalshi_market_id`; rekey sweep; title fallback | `weather_desk.py`, `hygiene.py`, `tasks.py`, `activity.py` |

Tests: `tests/test_loop34_data_quality.py` + updated weather/live_markets tests.

Never: resolve/settle, manual DB, frontend/deploy, weaken tests, push/merge.

---

## D3 — Gate + before/after + verifier

### Full gate (backend/)

```text
ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q -p no:cacheprovider
→ 1620 passed, 28 skipped in 314.21s

uv run --extra dev ruff check app tests
→ All checks passed!
```

### Honest before/after (local fixture + pure replay)

Prod DB not mutated (guardrail). Local Postgres auth unavailable for
`AsyncSessionLocal`; counts from pure-logic replay + pytest fixtures:

| metric | before | after |
|--------|-------:|------:|
| Exact title-dup groups (Mbappé props) | 1 | 0 (folded distinct titles) |
| Trump WC category | Sports | Politics |
| Egypt WC category | Sports | FIFA WC2026 |
| Weather signal market_id | `KXHIGHMIA-…` | `ks-kxhighmia-…` |
| Orphan raw-ticker rekey (fixture) | 1 raw | 0 raw / 1 canonical |
| Stale open past lock_at (fixture) | 1 OPEN | 0 OPEN (LOCKED) |
| missing-upstream Kalshi (fixture) | OPEN | LOCKED |

Script: `goals/loop-v34-dataquality/_d3_local_replay.py`

### Prod catalog (read-only baseline — not post-deploy)

| metric | prod 2026-07-15 |
|--------|----------------:|
| markets | 722 |
| open / locked / resolved | 378 / 198 / 146 |
| OPEN past lock_at | 0 |
| orphan signals in latest 200 | 19 |
| exact title-dup groups | 1 |

Post-deploy re-measure requires orchestrator merge + live workers; not claimed.

### Verifier (fresh context, re-ran commands)

```text
36 passed in 9.10s   PYTEST_EXIT=0
All checks passed!   RUFF_EXIT=0
VERDICT: PASS
```

Static: missing-upstream → `outcome=None` lock only; no frontend/deploy;
fixture coverage for fold / lapse / categories / rekey confirmed.

Earlier read-only verifier FAIL was tool-surface only (no shell); residual
`__all__` double-export + climate→Weather test fixed before re-verify.

---

## AutoLab
AutoLab: not applicable (one-shot data-quality repair, no iterative metric loop)

## Notes / residual
- Extreme-price OPEN longshots with future lock_at (186) left alone — honest.
- Weather markets still absent from catalog: rekey fixes join *when* KXHIGH
  markets are mirrored; until then city title fallback prevents blank labels.
- Large `_prod_*.json` dumps stay untracked (local audit only).
- Board-absence → lock can over-lock if Kalshi batch is partial (monitor).
