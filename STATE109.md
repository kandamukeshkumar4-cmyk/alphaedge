# STATE109 — Scanner DSL: CROSS_VENUE_DIVERGENCE + CLOSING_SOON

Worktree `E:/polymarket-worktrees/loop109-scannerdsl`, branch
`loop109-scannerdsl/node`, base `5482fab`. Research-only: scanners emit
signals/alerts, never orders. PAPER_TRADING_ONLY unchanged.

## 1. Confirmed before writing a line (file:line)

**Venue-gap data already exists — reused, no new matching logic.**
- `backend/app/db/models.py:681` `VenueMarketMatch` — persisted PM↔Kalshi pair
  (`pm_slug`, `ks_slug`, `confidence`, `stale`). Written by the venue-match
  worker, not by scanners.
- `backend/app/db/models.py:863` `VenueGap` — latest gap per matched pair:
  `pm_implied`, `ks_implied`, `gap` (pm − ks), `abs_gap`, `match_confidence`,
  `stale`, `captured_at`.
- `backend/app/services/venue_gap_service.py:30` `VenueGapService`;
  `:136` `gap_for_slug(slug)` returns the largest-`abs_gap` row touching a slug
  (matches on either `pm_slug` or `ks_slug`). This is exactly the "resolve the
  mirror pair for this market" primitive the step needs, so the executor calls
  it and builds nothing new. `refresh_gaps` (`:47`) is the write path and is
  NOT called from the scanner path.

**Lock timestamps already exist.**
- `backend/app/db/models.py:362` `Market.lock_at` — nullable, tz-aware.
  (`:624` is a second, unrelated model's `lock_at`; the scanner universe is
  built from `Market`, see `scanner_executor_service._load_universe`.)
- `Market.status == MarketStatus.OPEN` is already the universe filter in
  `_load_universe`, so "still open" is re-checked per candidate in the step for
  callers that assemble candidates directly.

**Compiler/executor/seed authorities confirmed as briefed:** allowed step set
`_KNOWN_STEP_TYPES` (compiler L31), write-side authority
`is_valid_compiled_spec`, warnings in `validate_spec`, empty-universe semantic
`status="empty" / error=None` in the executor — all left intact.

## 2. Design decision required by the brief (item 2)

**CLOSING_SOON is a STEP, not a universe filter.** Reason: `steps[]` is the
DSL's only validated, dispatchable extension point (schema-checked in
`is_valid_compiled_spec`, executed by `_run_step`, checkpointed per node),
whereas `universe` is a fixed two-key shape (`categories`, `minimum_volume`)
consumed by a single SQL query — adding a third key would need new universe
validation, new spec-shape handling in the API/frontend, and would not be
checkpointed. DIRECTION_ALIGNMENT is the existing precedent for a step that
filters rather than scores.

Related: `CROSS_VENUE_DIVERGENCE` was added to `_SIGNAL_TYPES` (it scores a
mispricing); `CLOSING_SOON` was deliberately NOT (it is a pure filter, so a
spec containing only CLOSING_SOON correctly warns "no signal steps").

## 3. What was built

| File | Change |
|---|---|
| `backend/app/services/scanner_compiler_service.py` | Both types added to `_KNOWN_STEP_TYPES` (L33-41); `CROSS_VENUE_DIVERGENCE` added to `_SIGNAL_TYPES` (L19-30); range constants (L48-55); `_step_min_gap` / `_step_within_hours` / `_valid_step_params` (L246-289) wired into `is_valid_compiled_spec`; three new `validate_spec` warnings (L413-431); planner system prompt documents both params (L67-70). |
| `backend/app/services/scanner_executor_service.py` | `_step_cross_venue_divergence` (L331-375) — `VenueGapService.gap_for_slug` per candidate, keep `abs_gap >= min_gap`, annotate both venue prices + gap + staleness, sort by `abs_gap` desc, **skip** unmirrored markets. `_step_closing_soon` (L378-421) — single `Market` lookup by slug, keep OPEN markets with `now <= lock_at <= now + within_hours`, annotate `hours_to_lock`, **skip** markets with no `lock_at`. Dispatch in `_run_step` (L458-471). |
| `backend/app/services/scanner_seed_service.py` | Two new public seeds, `owner=None`, `is_featured=False`; `is_featured` is now a per-entry key defaulting to `True` so the eight Loop107 starters keep their featured flag. |
| `backend/tests/test_loop109_scanner_dsl.py` | New — the 7 named tests. |
| `backend/tests/test_loop107_scanner_seeds.py` | **Out-of-charter, 1 line** — see §5. |

**Guardrail checks:** no `RiskService` / `OrderBookService` import in any
touched file; no LLM call added to executor or seed paths (the only LLM code in
the compiler is the pre-existing planner, untouched apart from its prompt
string); `CLOSING_SOON` compares against `datetime.now(UTC)` only and
`CROSS_VENUE_DIVERGENCE` reads only current `venue_gaps` rows — no resolution
or future data in either path. **Zero migrations** (both tables already exist);
no model/DDL change.

## 4. Verbatim proofs

```
$ cd backend && uv run --extra dev pytest -q tests/test_loop109_scanner_dsl.py tests/test_loop107_scanner_seeds.py --basetemp=E:/polymarket-worktrees/loop109-scannerdsl/.pt
...........                                                              [100%]
11 passed in 7.96s
```

```
$ cd backend && uv run --extra dev ruff check app tests
All checks passed!
```

```
$ cd backend && uv run --extra dev pytest -q tests/test_openapi_snapshot.py --basetemp=E:/polymarket-worktrees/loop109-scannerdsl/.pt2
...                                                                      [100%]
3 passed in 6.47s
```

```
$ cd backend && uv run --extra dev pytest -q --basetemp=E:/polymarket-worktrees/loop109-scannerdsl/.ptf
2142 passed, 28 skipped in 420.24s (0:07:00)
```

(OpenAPI snapshot passed unmodified — no route changes, as expected.)

## 5. Charter deviation (declared, 1 line)

`backend/tests/test_loop107_scanner_seeds.py:29` asserted
`5 <= len(STARTER_SCANNERS) <= 8`. The brief requires two new seeds in the same
catalog and requires that file to pass; both cannot hold. Widened the upper
bound to `10` and nothing else. No alternative avoids editing that file:
`main.py` (the only caller of `seed_starter_scanners`) is out of charter, so a
separate seed list cannot be wired, and a second list still breaks the same
file's `first == len(STARTER_SCANNERS)` assertion — a 2-line break instead of 1.

## 6. NEEDS / findings (listed, not fixed — extra scope is a defect)

1. **Frontend step-type mirror is stale.** `frontend/src/lib/scanners-api.ts:50`
   (`ScannerStepType` union), `:239` (step ordering list), `:481`/`:597`
   (read rendering), plus `ScannerCanvas.tsx:127`, `ScannerCard.tsx:28`,
   `ScannerDetailShell.tsx:92,763` all enumerate the five old step types.
   Specs containing the new types will render as unknown steps in Scanner
   Studio. Frontend is out of charter — needs a follow-up loop.
   (The backend planner prompt derives its list from `_KNOWN_STEP_TYPES`, so it
   needed no separate constant update; there is no other backend mirror.)
2. **"Cross-Venue Divergence" will never produce a `top_pick`.** A price gap
   has no direction, so per the brief the read carries no `direction`;
   `_is_aligned` therefore returns False and `top_pick` stays `None`
   (`run.status` is still `completed`). Whether the fired-alert path should
   treat a gap as directional (e.g. mirror price above local price ⇒ "up") is a
   product decision, deliberately not invented here.
3. **Stale venue gaps are kept, only annotated.** `gap_for_slug` returns the
   largest-`abs_gap` row regardless of `VenueGap.stale`, so a scanner can fire
   on an old quote pair. The read exposes `stale` and `match_confidence` so the
   UI can gate it; whether the step should hard-skip stale rows (or take a
   `min_confidence` param) was not in the brief.
4. **Seed 2 carries an extra signal step.** "Closing Soon, High Volume" is
   `[CLOSING_SOON within_hours=24, PRICE_TREND window_days=1]`. CLOSING_SOON is
   a filter, so a CLOSING_SOON-only spec trips the "no signal steps" warning
   that Loop107 requires every seed to avoid (`test_seeds_compile_through_the_
   real_compiler` asserts `validate_spec(spec) == []`). The PRICE_TREND step
   only annotates (it filters solely when DIRECTION_ALIGNMENT is present), so
   the seed's meaning is unchanged.
5. **Numeric strings are accepted for both new params** (`"24"`, `"0.05"`),
   matching the pre-existing `interval_minutes` check and
   `scanner_heal_service.coerce_numeric_strings`. Tightening the DSL to reject
   numeric strings would be a repo-wide convention change, not a Loop109 call.

## 7. Not done

No push. No deploy. No secret printed or set. No migration.
