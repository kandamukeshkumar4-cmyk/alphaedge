# STATE111-WIRING — Loop111 no-writer wiring node

Work order: `NOWRITER-SWEEP.md` (copied into this worktree root, cited by
`file:line` throughout).
Worktree: `E:/polymarket-worktrees/loop111-wiring`, branch `loop111-wiring/node`,
based on the integration tip `a086a3c` (`git -C E:/polymarket-worktrees/_integration rev-parse HEAD`).

Paper-trading simulation only. `PAPER_TRADING_ONLY` untouched. No order-path
imports, no LLM calls, no migrations (heads stay `066`), no look-ahead, no
secrets printed or set, no push, no deploy, no `git add -A`.

---

## Fix A — venue matching wired (sweep finding 1 / §2 row 1)

**Defect (sweep evidence):** `VenueMatchService.match_open_catalog()` →
`match_and_persist()` → `upsert_matches()` → `_upsert_one()`
(`backend/app/services/venue_match_service.py:141` writer) — *all four had zero
callers outside their own file*. `desk.py:89` calls only `list_matches()`, a read.
`venue_market_matches` was therefore permanently empty and the 60s venue gap loop
recomputed gaps over an empty match table. Prod corroboration in the sweep:
`/api/v1/system/loops` → `venue_gap running=True detail="upserted=0 skipped_odds=0"`,
`GET /api/v1/venue-gaps` → `{"gaps":[],"count":0}`, `GET /api/v1/arb/opportunities`
→ `{"opportunities":[],"total":0}`, `GET /api/v1/desk` → `"arb": null`.

**Wiring:**

| What | Where |
|---|---|
| Matcher invoked at the head of the existing task | `backend/app/workers/tasks.py:879` (`VenueMatchService(session).match_open_catalog(...)` inside `venue_gap_task`, before `VenueGapService.refresh_gaps()`) |
| Bounded per pass | `tasks.py:876` `match_limit = VENUE_GAP_MATCH_LIMIT` (existing knob, default 200) → passed as **both** `max_pairs` and the new `catalog_limit` |
| Per-venue catalog cap (new arg) | `backend/app/services/venue_match_service.py:82` (`catalog_limit`), applied at `:92-93` and implemented at `:130` `_open_by_source(..., limit=...)` |
| Idempotency (verified, not assumed) | `venue_match_service.py:139-168` `_upsert_one()` selects the existing `(pm_slug, ks_slug)` row and updates it; pinned by `test_venue_gap_task_invokes_matcher_and_persists_matches` (second pass, row count still 1) |
| Failure/empty isolation | `tasks.py:884-887` — matcher exception is caught, session rolled back, gap refresh still runs; `matched` reported as `None` |
| Observability | `backend/app/main.py:482` — `matched=` added to the `venue_gap` heartbeat detail |

**No look-ahead:** the `catalog_limit` cap orders by `Market.lock_at` ascending
(soonest-closing first). `lock_at` is scheduled market metadata, not an outcome
or a resolution timestamp. Documented in the service docstring.

**Confidence gate unchanged:** `match_open_catalog` keeps its `min_confidence=0.75`
default (strictly stricter than `VENUE_GAP_MIN_CONFIDENCE=0.5`, which the gap
service filters on), so nothing weaker than the already-tested gate is persisted.

**Tests (required by the work order):**
`test_venue_gap_task_invokes_matcher_and_persists_matches`,
`test_venue_gap_task_survives_empty_match_result`
— plus `test_venue_gap_task_survives_matcher_failure` and
`test_venue_gap_task_bounds_the_match_pass`.

---

## Fix B — whale positions live (sweep finding 2 / §3 AT-RISK #1)

### B(i) — dual-wired snapshot loop (done)

**Defect:** `snapshot_whale_positions_task` (`tasks.py`, `cron(..., minute=*/3)`
at `tasks.py:1330`) had **no in-process mirror** in `app/main.py`. Prod runs
uvicorn only (no ARQ worker), so `wallet_position_snapshots` and the whale-delta
`whale_events` had no production writer at all. Sweep prod evidence:
`GET /api/v1/smart-money` → `top_holders.wallet_count: 0`,
`recent_large_flows.whale_count: 0` (embedded verbatim in `GET /api/v1/desk`, and
consumed by `agents/tools.py:175,277`).

**Wiring — follows the `_prediction_writer_loop` / `_forecast_autolock_loop`
precedent exactly:**

| Precedent property | Implementation |
|---|---|
| In-process mirror | `backend/app/main.py:677` `_whale_positions_loop()` |
| **Never sleep-first**, boot catch-up FIRST | `main.py:697-707` — the boot pass runs before the `while True` at `main.py:709` (identical shape to `_prediction_writer_loop` at `main.py:649-659`) |
| Wall-clock pacing | `main.py:710-713` `_paced_sleep(max(60, WHALE_POSITIONS_INTERVAL_SEC=180), SCHEDULER_IDLE_INTERVAL_SEC)` |
| Single-flight | by construction — one task awaiting sequentially; no `asyncio.gather`, no nested `create_task` (asserted by the test). The precedent has no lock either. |
| Flag-gated (all 20 siblings are) | `main.py:928` `if settings.scheduler_whale_positions_enabled:` |
| Heartbeat on ok **and** error | `main.py:698/703/715/720` `record_heartbeat("whale_positions", ...)` |
| Bounded | `tasks.py:959` `WHALE_POSITION_WALLET_LIMIT = 50`; applied at `tasks.py:976,986` (`ORDER BY realized_pnl DESC LIMIT 50`) — one upstream HTTP call per wallet every ~3 min |
| Registry cadence advertised | `backend/app/observability/loop_state.py:42` `"whale_positions": 180` |

New settings (`backend/app/core/config.py:107-116`):
`SCHEDULER_WHALE_POSITIONS_ENABLED` (default `true`),
`WHALE_POSITIONS_INTERVAL_SEC` (default `180`).

### B(ii) — `record_wallet_positions` caller: **NEEDS DESIGN (not guessed)**

The work order permits recording rather than guessing when the intended caller is
genuinely ambiguous. It is. Evidence from reading the service and the task:

1. **Type mismatch.** `WalletService.record_wallet_positions(platform, positions)`
   (`backend/app/services/wallet_service.py:23`) takes
   `list[OnchainWalletPosition]` — `backend/app/data/connectors/onchain.py:89-102`:
   `roi`, `hit_rate`, `realized_pnl`, `unrealized_pnl`, `total_pnl`,
   `total_trades`, `side`, `current_price`. The snapshot task's data source is
   `PolymarketDataApiConnector.fetch_positions()`
   (`polymarket_data_api.py:209`) which yields `WalletPositionRow`
   (`polymarket_data_api.py:39-45`): only `market_id`, `market_slug`, `outcome`,
   `size`, `avg_price`. **Every PnL/ROI/hit-rate field would have to be
   fabricated** to call it from there — a truth-first violation, and exactly the
   class of fake-data defect this loop family exists to remove.
2. **Destructive side effect.** `record_wallet_positions` also *writes*
   `TrackedWallet.realized_pnl/roi/hit_rate/total_trades/qualified`
   (`wallet_service.py:32-43`). Those are owned by the weekly
   `refresh_whales_task` → `WhaleTrackerService.upsert_qualification`. Wiring it
   into a 3-minute loop with fabricated inputs would silently overwrite the real
   qualifier and could disqualify every tracked wallet.
3. **Its actual designed caller is also dead.**
   `OnchainReadOnlyConnector.fetch_wallet_positions()` (`onchain.py:39`) is the
   only producer of `OnchainWalletPosition`, and it has **zero production
   callers** (only `tests/test_data_connectors.py:523` and
   `tests/test_http_connector_resilience.py:214`). So the correct fix is a
   product decision about the *subgraph* ingest path, not a wiring edit.

**NEEDS DESIGN: `record_wallet_positions` caller.** The sweep itself frames this
as a two-store root cause (`NOWRITER-SWEEP.md:148`): either build the subgraph
ingest path that feeds `wallet_positions`, or retire
`GET /api/v1/signals/smart-money` in favour of `GET /api/v1/smart-money`, which
reads `wallet_position_snapshots` — the store Fix B(i) just gave a live writer.
Deciding that is out of scope for a wiring node.

**Tests:** `test_whale_snapshot_loop_registered_and_wallclock` (drives the real
`lifespan`, asserts the loop is registered, uses `_paced_sleep`, calls the task
before `while True`, and has no fan-out), plus
`test_whale_snapshot_task_is_bounded_per_pass` and
`test_whale_positions_loop_is_flag_gated`.

---

## Fix C — loops visibility (sweep §3b)

**Defect:** `app/api/v1/system.py:42` iterated a hardcoded `_ALL_LOOPS` tuple (26
entries) that had drifted behind the loop registry. Six loops that do record
heartbeats were invisible on `GET /api/v1/system/loops`: `prediction_writer`,
`scanner_scheduler`, `news_mispricing`, `unusual_flow`, `alpha_model`,
`notification_digest`. Sweep prod check: the endpoint returned 26 rows and omitted
`prediction_writer` even though `LOOP_INTERVALS` contains it.

**Wiring:**

- `backend/app/api/v1/system.py:42` — `_ALL_LOOPS` is now
  `tuple(LOOP_INTERVALS.keys())`, derived from the authoritative registry
  `backend/app/observability/loop_state.py:29`. A future loop registered there
  appears automatically. Kept as a module constant because four existing tests
  (`test_external_market_bridge.py:510`, `test_heartbeat_guards.py:60`,
  `test_loop58_data_pipeline.py:386`, `test_pods_runner.py:9`) assert membership
  against it — those keep passing untouched.
- `system.py:45` `_all_loops(beats)` additionally unions in any loop that has
  actually recorded a heartbeat but is not in the registry, so an unregistered
  live loop is surfaced rather than silently dropped. This is what makes
  `alpha_model` / `notification_digest` (which beat but are not in
  `LOOP_INTERVALS`) visible without editing four more files.
- `system.py:74` — the endpoint iterates `_all_loops(beats)`.

**Honesty preserved:** names come only from the registry or a real heartbeat —
nothing is invented — and a loop with no beat still reports `status:"never"`,
`running:false`, `last_heartbeat:null`. Pinned by
`test_system_loops_endpoint_reports_the_derived_list`.

**Test:** `test_system_loops_covers_all_registered_loops` — asserts
`prediction_writer` present and `len(_ALL_LOOPS) >= len(LOOP_INTERVALS)` (plus
the registry is a subset, an unregistered beating loop is surfaced, and no loop
is invented).

**Response shape:** unchanged. Same keys per row (`name`, `planned`, `running`,
`status`, `last_heartbeat`, `interval_sec`, `detail`) and same top-level shape
(`plan`, `loops`, `paper_trading_only`). Only the *contents* of the `loops` list
grew. The route is declared `-> dict[str, Any]`, so the OpenAPI schema is
byte-identical — **no snapshot regeneration was needed** (see the snapshot test
result below, run without any regen).

---

## STOP CONDITION — verbatim command output

All commands run from `E:/polymarket-worktrees/loop111-wiring/backend` on the
final committed tree (verified byte-identical to the tree the full suite ran on).

### 1. Targeted pytest for the new test file

```
$ uv run --extra dev pytest tests/test_loop111_wiring.py -q -p no:cacheprovider
9 passed in 6.36s
```

### 2. ruff

```
$ uv run --extra dev ruff check app tests
All checks passed!
```

### 3. alembic heads (must stay 066)

```
$ uv run --extra dev alembic heads
066_alpha_validation (head)
```

Zero migrations added, as expected — all tables already exist.

### 4. OpenAPI snapshot + authz matrix

```
$ uv run --extra dev pytest tests/test_openapi_snapshot.py tests/test_loop26_authz_matrix.py -q -p no:cacheprovider
5 passed in 21.84s
```

No snapshot regeneration required: `GET /api/v1/system/loops` is typed
`-> dict[str, Any]`, so its schema did not change.

### 5. FULL suite summary line

```
$ uv run --extra dev pytest -q -p no:cacheprovider
2151 passed, 28 skipped in 410.57s (0:06:50)
```

Note: on Windows pytest emits `PytestWarning: (rm_rf) error removing ...
garbage-*` tmpdir-cleanup warnings and an atexit `PermissionError` on
`pytest-current`. These are pre-existing environment noise (tmpdir teardown on
NTFS), not test failures — `-p no:cacheprovider` is used only to keep that noise
from burying the summary line.

---

## Commits

| Commit | Fix |
|---|---|
| `12a28aa` | `fix(loop111): wire the venue matcher into venue_gap_task` |
| `30dc4da` | `fix(loop111): dual-wire the whale position snapshot loop in main.py` |
| `f6fc6ae` | `fix(loop111): derive /system/loops from the loop registry, add wiring tests` |

Diff across the three commits:

```
 backend/app/api/v1/system.py                |  57 +++--
 backend/app/core/config.py                  |   9 +
 backend/app/main.py                         |  53 +++++
 backend/app/observability/loop_state.py     |   1 +
 backend/app/services/venue_match_service.py |  20 +-
 backend/app/workers/tasks.py                |  41 +++-
 backend/tests/test_loop111_wiring.py        | 340 ++++++++++++++++++++++++++++
 7 files changed, 484 insertions(+), 37 deletions(-)
```

---

## Charter compliance and deltas

In charter, as written: `backend/app/workers/tasks.py` (venue gap task + the
whale task's bound), `backend/app/main.py` (one new loop block + one heartbeat
detail line), `backend/app/api/v1/system.py`,
`backend/app/services/venue_match_service.py` (the venue service file, only where
the wiring demanded a bound), `backend/tests/test_loop111_wiring.py`,
`STATE111-WIRING.md`.

Two files outside the literal charter list were touched, both minimally and both
demanded by the Fix B loop block. Declared here rather than hidden:

1. `backend/app/core/config.py` (+9 lines) — `SCHEDULER_WHALE_POSITIONS_ENABLED`
   and `WHALE_POSITIONS_INTERVAL_SEC`. Every one of the 20 sibling in-process
   mirrors is individually flag-gated; shipping an ungated always-on loop would
   have broken the precedent the work order told me to follow exactly.
2. `backend/app/observability/loop_state.py` (+1 line) — `"whale_positions": 180`
   in `LOOP_INTERVALS`. Without it the new loop would report a `null` cadence on
   the very endpoint Fix C exists to make trustworthy.

Untouched, as required: `backend/app/alpha/**`, opportunities gating,
`frontend/**`, `PAPER_TRADING_ONLY`, all Alembic migrations.

## Guardrail check

- `PAPER_TRADING_ONLY`: not read, not written, not weakened. Still asserted true
  by `test_system_loops_endpoint_reports_the_derived_list`.
- Order path: no import of `RiskService` / `OrderIntent` / `OrderBookService`
  anywhere in this diff. Nothing in it can create an order.
- LLM: no LLM/agent call added. Fix A is deterministic string/entity matching;
  Fix B is a bounded read-only HTTP fan-out + diff; Fix C is pure aggregation.
- Look-ahead: none. The only new ordering key is `Market.lock_at` (scheduled
  metadata) for the catalog cap; `TrackedWallet.realized_pnl` for the wallet cap
  is already-realised history, not future information.
- Secrets: none printed, set, or read.
- No push, no deploy, no `git add -A` (every commit staged explicit paths).

## AutoLab

AutoLab: not applicable (no iterative measure) — this is a one-shot wiring node.
The measurable axes it unblocks (`venue_gaps` / `arb` population,
`wallet_position_snapshots` fill rate) can only be measured against production
after deploy, which is explicitly out of this node's scope.

## Open items for the next node

- **NEEDS DESIGN: `record_wallet_positions` caller** — see Fix B(ii) above.
  Requires a product decision between building the subgraph ingest path and
  retiring `GET /api/v1/signals/smart-money` in favour of `GET /api/v1/smart-money`.
- Untouched sweep findings, listed for the backlog, not claimed as done:
  `evaluations` NO-WRITER (§2 #4), `push_subscriptions` NO-READER (§2 #5),
  `backtest_runs` cron-only writer (§2 #6 / §3 #3), the 8 DORMANT tables (§2 #7),
  and the remaining AT-RISK cron-only writers §3 #2, #4, #5, #6, #7, #8.
- `news_mispricing` and `unusual_flow` are started by the lifespan but record no
  heartbeat at all (grep: zero `record_heartbeat` calls for either name), so Fix C
  cannot surface them — they will show as absent, not as `never`. Giving those two
  loops heartbeats is a small follow-up.
