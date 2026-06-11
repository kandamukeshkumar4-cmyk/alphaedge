---
id: loop-x-mirror-mvp
phase: loop-x
status: QUEUED
depends_on: [phase-3-forecast-engine, phase-6-overlay-tracking]
workflow: backend-feature + ui-feature
executor: Composer 2.5 (low-reasoning — follow tasks literally, in order, one at a time)
---

# Loop X — AlphaEdge Mirror MVP (forecasting-skill tracker, paper/research only)

> **EXECUTOR PROTOCOL (read first):** Execute Tasks 1–15 strictly in order. Do not
> skip, reorder, or merge tasks. After each task, run that task's **Gate** command
> and do not continue until it passes. If a gate fails, fix only the files named in
> that task. Never edit files outside the lists given per task.

## Why now

AlphaEdge Mirror ("Strava for prediction-market forecasting") is the
user-facing proof layer: users lock probability forecasts on Polymarket and
Kalshi markets, the backend snapshots the official market implied probability
server-side, and users are scored after resolution (Brier, edge-over-market,
calibration, synthetic paper P&L). Phases 3/4/6 shipped the engine and overlay;
this loop closes the remaining MVP gaps so the Mirror track record is complete,
honest, and shippable.

## Repo reality (IMPORTANT — this is a close-the-gaps loop, not greenfield)

Most of the Mirror MVP **already exists and is tested**. Do NOT recreate it:

- DB models `Forecaster`, `ExternalMarket`, `MarketSnapshot`, `ForecastLog`
  (append-only), `ForecastScore` already exist in `backend/app/db/models.py`
  (lines ~523–701), created by migrations `004_forecast_ledger.py` →
  `007_forecaster_recovery_code.py`. Latest migration is
  `019_audit_hardening_indexes.py`; new migrations start at **020**.
- Endpoints `POST /api/v1/forecasters/anonymous`, `POST
  /api/v1/markets/external/resolve-url`, `POST /api/v1/forecasts`, `GET
  /api/v1/forecasters/me/dashboard`, `GET /api/v1/backfill/markets`, `POST
  /api/v1/admin/external-markets/{id}/resolve` already exist in
  `backend/app/api/v1/forecast_routes.py` (registered in `app/main.py` as
  `forecast_router`).
- URL parsers + httpx adapters (`PolymarketGammaAdapter`, `KalshiRestAdapter`,
  `ManualAdapter`, `register_adapter` mock seam) exist in
  `backend/app/forecasting/market_source.py`.
- Pure scoring math (Brier, anchoring epsilon `ANCHOR_EPSILON = 0.02`,
  synthetic P&L) exists in `backend/app/forecasting/scoring.py`; constants in
  `backend/app/forecasting/__init__.py` (`BRIER_MIN_SAMPLE = 30`,
  `CALIBRATION_MIN_SAMPLE = 150`); DB scoring in
  `backend/app/services/scoring_service.py` (incl. leakage gate).
- Dashboard aggregation (timing buckets `7d+ / 1-7d / 6-24h / 1-6h / <1h /
  unknown`, calibration bins, provisional flags, category `< 20` provisional)
  exists in `backend/app/services/forecast_dashboard_service.py`.
- Web dashboard exists at `frontend/src/app/forecast/page.tsx` with API client
  `frontend/src/lib/forecast-mirror-api.ts` and view-model
  `frontend/src/lib/forecast-dashboard-view-model.ts`.
- Chrome MV3 extension (React+TS, Vite) exists in `extension/` with Shadow DOM
  overlay (`src/content/overlay.tsx`, `src/content/overlay-host.ts`), popup,
  service worker (`src/background.ts`), queue, telemetry, and vitest tests.

**Deviations from the original spec, forced by repo reality** (already decided —
do not revisit):

1. Tasks are "verify + extend", not "create": models/endpoints/adapters exist.
2. The dashboard page lives at `/forecast`; this loop ADDS the `/mirror` route
   re-using the same component (Task 10) instead of duplicating 30 KB of UI.
3. The anchored flag is stored inverted as `ForecastLog.is_independent`
   (anchored == `not is_independent`). Keep that name.
4. FanDuel is currently half-present (parser maps it to `Platform.MANUAL`;
   extension manifest includes the host). The spec defers FanDuel entirely, so
   this loop REMOVES those FanDuel hooks (Tasks 4, 13).
5. New scoring metrics that genuinely don't exist yet: first-independent-
   forecast score and time-weighted path score (Tasks 5–7).

## Scope summary (verbatim product scope — do not expand)

AlphaEdge Mirror MVP — a paper/research-only forecasting-skill tracker. Users
lock probability forecasts on Polymarket and Kalshi markets; the AlphaEdge
backend snapshots official market implied probability server-side, then scores
users after resolution. NO betting execution, NO wallet/key storage, NO
sportsbook automation, NO copy trading, NO real-money order flows, NO FanDuel
scraping (FanDuel deferred entirely; web dashboard first, Chrome extension as
the final tasks).

## Hard guardrails (non-negotiable)

- **Paper/research only.** `PAPER_TRADING_ONLY=true` stays required; do not
  touch the validator in `backend/app/core/config.py` (`must_be_paper_only`).
- **No order-path changes.** Do not modify `RiskService`, `OrderIntent`,
  `OrderBookService`, `backend/app/api/v1/orders.py`, or anything under
  `backend/app/risk/`. Mirror never executes anything.
- **Append-only forecast log.** `forecast_logs` rows are immutable; no
  UPDATE/DELETE endpoints, no edit UI. Belief updates are new rows (`seq + 1`).
- **Unresolved markets never produce scores** (leakage gate in
  `ScoringService.score_market` stays intact).
- **No credentials client-side.** Kalshi/Polymarket config stays in backend
  `Settings`; never returned by any response schema; no password/key fields in
  any UI.
- Banned copy anywhere in new UI: "place bet", "auto bet", "guaranteed
  profit", "wallet", "private key", "real-money".

---

## Tasks (execute strictly in order)

### Task 1 — Record the green baseline

**Modify:** nothing. **Create:** nothing.

Run all three suites and record the passing counts (you will reuse them in the
Task 15 PR line). All must pass before any edit. From the repo root
`E:\polymarket clone`:

1. `cd backend && uv run --extra dev pytest -q && uv run --extra dev ruff check app tests`
2. `cd frontend && npm run typecheck && npm run lint && npm run test`
3. `cd extension && npm run typecheck && npm run test`

**Gate:** `cd backend && uv run --extra dev pytest -q` (exit code 0; note the count, e.g. `NNN passed`).

---

### Task 2 — Migration 020: dashboard/backfill indexes

**Create:** `backend/alembic/versions/020_mirror_dashboard_indexes.py`
**Modify:** `backend/app/db/models.py`

The dashboard queries filter `forecast_logs` by forecaster ordered by
`locked_at`, and `GET /api/v1/backfill/markets` filters
`external_markets.status`. Add covering indexes.

New migration file (follow the exact style of `019_audit_hardening_indexes.py`):

```python
"""mirror dashboard indexes

Revision ID: 020_mirror_dashboard_indexes
Revises: 019_audit_hardening_indexes
Create Date: 2026-06-11
"""

from typing import Sequence, Union

from alembic import op

revision: str = "020_mirror_dashboard_indexes"
down_revision: Union[str, Sequence[str], None] = "019_audit_hardening_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_external_markets_status", "external_markets", ["status"])
    op.create_index(
        "ix_forecast_logs_forecaster_locked",
        "forecast_logs",
        ["forecaster_id", "locked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_forecast_logs_forecaster_locked", table_name="forecast_logs")
    op.drop_index("ix_external_markets_status", table_name="external_markets")
```

In `backend/app/db/models.py`:

- `ExternalMarket.__table_args__`: add `Index("ix_external_markets_status", "status")`
  to the existing tuple (keep the existing unique platform/external_id index).
- `ForecastLog.__table_args__`: add
  `Index("ix_forecast_logs_forecaster_locked", "forecaster_id", "locked_at")`
  to the existing tuple. Change nothing else in either model.

**Gate:** `cd backend && uv run alembic heads && uv run --extra dev pytest -q tests/test_forecast_mirror.py`
(heads must print `020_mirror_dashboard_indexes (head)`; tests pass.)

---

### Task 3 — Server-side adapter config (Kalshi creds + base URLs)

**Modify:** `backend/app/core/config.py`, `backend/app/forecasting/market_source.py`, `.env.example`

In `Settings` (`backend/app/core/config.py`), directly below the existing
`kalshi_market_tickers` field, add four fields (server-side only; never sent to
any client):

```python
    polymarket_gamma_base_url: str = Field(
        default="https://gamma-api.polymarket.com", alias="POLYMARKET_GAMMA_BASE_URL"
    )
    kalshi_api_base_url: str = Field(
        default="https://external-api.kalshi.com/trade-api/v2", alias="KALSHI_API_BASE_URL"
    )
    kalshi_api_key_id: str = Field(default="", alias="KALSHI_API_KEY_ID")
    kalshi_private_key_pem: str = Field(default="", alias="KALSHI_PRIVATE_KEY_PEM")
```

In `backend/app/forecasting/market_source.py`, replace the module-level
`_ADAPTERS = {...}` dict literal with lazy construction so settings are read at
first use (do NOT import `get_settings` at module top-of-file scope into the
adapters themselves; import inside the builder to avoid env-load ordering
issues):

```python
_ADAPTERS: dict[Platform, MarketDataAdapter] = {}


def _build_default_adapters() -> dict[Platform, MarketDataAdapter]:
    from app.core.config import get_settings

    settings = get_settings()
    return {
        Platform.POLYMARKET: PolymarketGammaAdapter(settings.polymarket_gamma_base_url),
        Platform.KALSHI: KalshiRestAdapter(settings.kalshi_api_base_url),
        Platform.MANUAL: ManualAdapter(),
    }


def get_adapter(platform: Platform) -> MarketDataAdapter:
    if not _ADAPTERS:
        _ADAPTERS.update(_build_default_adapters())
    return _ADAPTERS.get(platform, ManualAdapter())
```

Keep `register_adapter` exactly as-is (tests rely on it). The Kalshi credential
fields are intentionally unused by the public read-only endpoints in this loop;
they exist so a deployment can add authenticated reads WITHOUT any client-side
key handling. Do not add request signing in this loop.

In `.env.example`, append (with empty values):
`POLYMARKET_GAMMA_BASE_URL=`, `KALSHI_API_BASE_URL=`, `KALSHI_API_KEY_ID=`,
`KALSHI_PRIVATE_KEY_PEM=`.

In `backend/tests/test_config.py`, append:

```python
def test_market_adapter_settings_have_safe_defaults():
    settings = Settings(APP_ENV="development")

    assert settings.polymarket_gamma_base_url == "https://gamma-api.polymarket.com"
    assert settings.kalshi_api_base_url == "https://external-api.kalshi.com/trade-api/v2"
    assert settings.kalshi_api_key_id == ""
    assert settings.kalshi_private_key_pem == ""
```

**Gate:** `cd backend && uv run --extra dev pytest -q tests/test_config.py tests/test_forecast_mirror.py`

---

### Task 4 — Remove FanDuel from the URL parser (deferred entirely)

**Modify:** `backend/app/forecasting/market_source.py`,
`backend/app/services/external_market_service.py`, `backend/tests/test_forecast_mirror.py`

1. In `market_source.py`: delete the `_FANDUEL_HOSTS` constant and the entire
   `if host in _FANDUEL_HOSTS:` block inside `parse_market_url` (FanDuel URLs
   must now return `None`). Update the module docstring sentence that mentions
   FanDuel, if any.
2. In `external_market_service.py` line ~46, change the error string to:
   `"Unrecognized market URL (Polymarket and Kalshi only)"`.
3. In `backend/tests/test_forecast_mirror.py`: the constant
   `FANDUEL_URL = "https://sportsbook.fanduel.com/navigation/nba"` stays, but
   rewrite every test that asserts FanDuel parses to `Platform.MANUAL` into a
   single test:

```python
def test_fanduel_urls_are_rejected_deferred():
    assert parse_market_url(FANDUEL_URL) is None
```

   Also update any test asserting the old error message text to the new
   "(Polymarket and Kalshi only)" string.

**Gate:** `cd backend && uv run --extra dev pytest -q tests/test_forecast_mirror.py && uv run --extra dev ruff check app tests`

---

### Task 5 — Pydantic schemas for the new metrics + optional recovery email

**Modify:** `backend/app/schemas/forecast.py`

1. In `DashboardMetrics`, after `synthetic_pnl_total: float`, add three fields
   (defaults required so the service compiles before Task 7 wires them):

```python
    first_independent_count: int = 0
    first_independent_mean_brier: Optional[float] = None
    time_weighted_brier: Optional[float] = None
```

2. Above `ForecasterCreateResponse`, add a new request model (the existing
   endpoint takes no body today; the body becomes optional):

```python
class ForecasterCreateRequest(BaseModel):
    recovery_email: Optional[str] = Field(
        default=None, max_length=255, description="Optional email for recovery only."
    )
```

Change nothing else in this file.

**Gate:** `cd backend && uv run --extra dev pytest -q tests/test_forecast_mirror.py tests/test_forecast_dashboard.py`

---

### Task 6 — Pure scoring math: first-independent + time-weighted path score

**Modify:** `backend/app/forecasting/scoring.py`
**Create:** `backend/tests/test_mirror_path_scores.py`

Append to `scoring.py` (pure functions, no DB/I-O, matching the module's
existing conventions — probabilities are P(YES), `outcome` is 0/1):

```python
@dataclass(frozen=True)
class PathPoint:
    """One locked forecast on a market's timeline (seconds are absolute epochs
    or any monotone clock; only differences are used)."""

    locked_at_seconds: float
    user_probability: float
    is_independent: bool


def first_independent_brier(points: list[PathPoint], outcome: int) -> Optional[float]:
    """Brier of the FIRST independent forecast on a market (earliest lock).
    Returns None when no independent forecast exists."""
    ordered = sorted(points, key=lambda p: p.locked_at_seconds)
    for point in ordered:
        if point.is_independent:
            return brier(point.user_probability, outcome)
    return None


def time_weighted_path_brier(
    points: list[PathPoint], outcome: int, close_at_seconds: float
) -> Optional[float]:
    """Time-weighted Brier over a forecaster's full belief path on one market.

    Each forecast is weighted by the fraction of [first_lock, close) during
    which it was the forecaster's current belief. Returns None when there are
    no points or the close time is not strictly after the first lock.
    """
    ordered = sorted(points, key=lambda p: p.locked_at_seconds)
    if not ordered:
        return None
    start = ordered[0].locked_at_seconds
    total = close_at_seconds - start
    if total <= 0:
        return None
    weighted = 0.0
    for index, point in enumerate(ordered):
        end = (
            ordered[index + 1].locked_at_seconds
            if index + 1 < len(ordered)
            else close_at_seconds
        )
        end = min(end, close_at_seconds)
        duration = max(end - point.locked_at_seconds, 0.0)
        weighted += (duration / total) * brier(point.user_probability, outcome)
    return weighted
```

Add the `dataclass` import only if not already imported (it is — line 12).

Create `backend/tests/test_mirror_path_scores.py` with these pure tests
(plain `pytest`, no fixtures needed):

```python
from app.forecasting.scoring import (
    PathPoint,
    brier,
    first_independent_brier,
    time_weighted_path_brier,
)


def test_first_independent_brier_picks_earliest_independent():
    points = [
        PathPoint(locked_at_seconds=100.0, user_probability=0.55, is_independent=False),
        PathPoint(locked_at_seconds=200.0, user_probability=0.70, is_independent=True),
        PathPoint(locked_at_seconds=300.0, user_probability=0.90, is_independent=True),
    ]
    assert first_independent_brier(points, outcome=1) == brier(0.70, 1)


def test_first_independent_brier_none_when_all_anchored():
    points = [PathPoint(100.0, 0.55, False)]
    assert first_independent_brier(points, outcome=0) is None


def test_time_weighted_path_brier_weights_by_holding_duration():
    # Held 0.40 for 75% of the window, 0.80 for the final 25%; outcome YES.
    points = [PathPoint(0.0, 0.40, True), PathPoint(75.0, 0.80, True)]
    expected = 0.75 * brier(0.40, 1) + 0.25 * brier(0.80, 1)
    assert abs(time_weighted_path_brier(points, 1, close_at_seconds=100.0) - expected) < 1e-9


def test_time_weighted_path_brier_none_without_close_window():
    points = [PathPoint(100.0, 0.40, True)]
    assert time_weighted_path_brier(points, 1, close_at_seconds=100.0) is None
    assert time_weighted_path_brier([], 1, close_at_seconds=100.0) is None
```

**Gate:** `cd backend && uv run --extra dev pytest -q tests/test_mirror_path_scores.py`

---

### Task 7 — Wire the new metrics into the dashboard service

**Modify:** `backend/app/services/forecast_dashboard_service.py`

In the method that builds the live `DashboardMetrics` (the one constructing
`DashboardMetrics(... synthetic_pnl_total=pnl_total, ...)` around line 210):

1. Import at the top of the file:
   `from app.forecasting.scoring import PathPoint, first_independent_brier, time_weighted_path_brier`.
2. Before constructing `DashboardMetrics`, group the live scored rows by
   `external_market_id` and compute:

```python
        by_market: dict = {}
        for r in live_scored:
            by_market.setdefault(r.forecast.external_market_id, []).append(r)

        first_independent_values: list[float] = []
        path_values: list[float] = []
        for rows in by_market.values():
            outcome = rows[0].score.actual_outcome
            points = [
                PathPoint(
                    locked_at_seconds=r.forecast.locked_at.timestamp(),
                    user_probability=float(r.forecast.user_probability),
                    is_independent=r.forecast.is_independent,
                )
                for r in rows
            ]
            fib = first_independent_brier(points, outcome)
            if fib is not None:
                first_independent_values.append(fib)
            close_at = rows[0].forecast.external_market.close_at
            resolved_at = rows[0].forecast.external_market.resolved_at
            window_end = close_at or resolved_at
            if window_end is not None:
                path = time_weighted_path_brier(points, outcome, window_end.timestamp())
                if path is not None:
                    path_values.append(path)
```

   Note: `live_scored` rows must have `external_market` loaded; the service
   already joins `ExternalMarket` for the category breakdown — reuse whatever
   loaded attribute pattern the file already uses (if it keys category off a
   joined tuple instead of a relationship, mirror that access pattern here).
   If `locked_at` can be timezone-naive (SQLite tests), normalize with the
   file's existing `_as_aware`-style helper before calling `.timestamp()`.
3. Pass into `DashboardMetrics(...)`:

```python
            first_independent_count=len(first_independent_values),
            first_independent_mean_brier=_mean(first_independent_values),
            time_weighted_brier=_mean(path_values),
```

   (`_mean` already exists in this file and returns `None` for empty lists.)

Append to `backend/tests/test_mirror_path_scores.py` an integration test that
creates a forecaster, one external market with `close_at` set, two locked
forecasts (an anchored one then an independent one), admin-resolves it, scores
it, builds the dashboard, and asserts `first_independent_count == 1`,
`first_independent_mean_brier is not None`, `time_weighted_brier is not None`.
Copy the fixture/client pattern from `backend/tests/test_forecast_mirror.py`
verbatim (the `_no_live_market_adapters` autouse fixture, `db_session` from
`conftest.py`, `AsyncClient(transport=ASGITransport(app=app), ...)`, and the
`app.dependency_overrides[get_db]` override used there).

**Gate:** `cd backend && uv run --extra dev pytest -q tests/test_mirror_path_scores.py tests/test_forecast_dashboard.py`

---

### Task 8 — Optional recovery email on anonymous forecaster creation

**Modify:** `backend/app/api/v1/forecast_routes.py`

Change the `create_forecaster` endpoint to accept an optional JSON body using
the Task 5 schema (existing no-body callers must keep working):

```python
@router.post("/forecasters/anonymous", response_model=ForecasterCreateResponse)
async def create_forecaster(
    body: ForecasterCreateRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    service = ForecasterService(db)
    forecaster, raw_token, recovery_code = await service.create_anonymous()
    if body is not None and body.recovery_email:
        await service.attach_recovery_email(forecaster, body.recovery_email)
    return ForecasterCreateResponse(
        id=forecaster.id,
        token=raw_token,
        recovery_code=recovery_code,
        disclaimer=PAPER_TRADING_DISCLAIMER,
    )
```

Add `ForecasterCreateRequest` to the existing `app.schemas.forecast` import
list. `ForecasterService.attach_recovery_email` already exists
(`backend/app/services/forecaster_service.py`) and stores only a hash — do not
modify it.

Append two tests to `backend/tests/test_mirror_path_scores.py`:
- POST `/api/v1/forecasters/anonymous` with no body → 200, token returned.
- POST with `{"recovery_email": "a@b.co"}` → 200, and the stored
  `Forecaster.recovery_email_hash` is not None (query via `db_session`); assert
  the raw email string does not appear in the response body.

**Gate:** `cd backend && uv run --extra dev pytest -q tests/test_mirror_path_scores.py tests/test_forecast_mirror.py`

---

### Task 9 — Backend integrity tests (append-only, epsilon, buckets, leakage)

**Modify:** `backend/tests/test_mirror_path_scores.py` (append a
`class`-free section of tests; reuse the same fixtures)

Add exactly these tests (skip any that already exist verbatim in
`test_forecast_mirror.py` — check first; do not duplicate):

1. `test_forecast_log_has_no_update_routes` — assert the FastAPI app exposes no
   `PUT`/`PATCH`/`DELETE` method for the `/api/v1/forecasts` path:

```python
def test_forecast_log_has_no_update_routes():
    from app.main import app as fastapi_app

    for route in fastapi_app.routes:
        if getattr(route, "path", "") == "/api/v1/forecasts":
            assert route.methods == {"POST"}
```

2. `test_anchoring_epsilon_boundary` — pure: `scoring.is_independent(0.50, 0.52)`
   is True (diff == 0.02 counts as independent) and
   `scoring.is_independent(0.50, 0.519)` is False.
3. `test_time_bucket_boundaries` — import `_time_bucket` from
   `app.services.forecast_dashboard_service` and assert: 8 days → `"7d+"`,
   2 days → `"1-7d"`, 12 hours → `"6-24h"`, 3 hours → `"1-6h"`, 30 minutes →
   `"<1h"`, `None` → `"unknown"` (build a `ForecastLog` instance in memory with
   only `time_to_resolution_seconds` set).
4. `test_unresolved_market_never_scores` — create market + forecast, do NOT
   resolve, call `ScoringService(db).score_market(market)` and assert it raises
   `ValueError`; then assert `forecast_scores` is empty via
   `select(ForecastScore)`.
5. `test_admin_resolve_requires_admin_key_and_scores` — POST
   `/api/v1/admin/external-markets/{id}/resolve` without `X-Admin-Key` header →
   401/403; with the dev key (see how `test_forecast_mirror.py` passes admin
   auth) → 200 and one `ForecastScore` row exists with correct
   `user_brier == (p - outcome) ** 2`.

**Gate:** `cd backend && uv run --extra dev pytest -q tests/test_mirror_path_scores.py`

---

### Task 10 — Frontend `/mirror` route + surface new metrics

**Create:** `frontend/src/app/mirror/page.tsx`
**Modify:** `frontend/src/lib/forecast-mirror-api.ts`,
`frontend/src/lib/forecast-dashboard-view-model.ts`, `frontend/src/components/SiteHeader.tsx`

1. New route file — re-export the existing dashboard page (do not duplicate UI):

```tsx
export { default } from "../forecast/page";
```

2. In `forecast-mirror-api.ts`, extend the `DashboardMetrics`-equivalent type
   (the `live` object inside `ForecastDashboard`) with the three new fields the
   backend now returns:

```ts
  first_independent_count: number;
  first_independent_mean_brier: number | null;
  time_weighted_brier: number | null;
```

3. In `forecast-dashboard-view-model.ts`, surface them on the returned view
   model as two display rows with provisional handling, mirroring the file's
   existing patterns: `firstIndependentBrier` (label `"First independent
   forecast (Brier)"`, value `null` → `"—"`) and `timeWeightedBrier` (label
   `"Time-weighted path (Brier)"`). Reuse the existing provisional rule: mark
   provisional when `live.resolved_count < 30`.
4. In `SiteHeader.tsx`, add one nav link `Mirror` → `/mirror` next to the
   existing `Forecast` (or equivalent) nav entry, copying the exact JSX pattern
   of a neighboring link.

**Gate:** `cd frontend && npm run typecheck && npm run lint`

---

### Task 11 — Frontend vitest: provisional labels + empty states

**Modify:** `frontend/src/lib/forecast-dashboard-view-model.test.ts`

Append tests following the file's existing builder/assert style:

1. `provisional label shown when resolved_count < 30` — build a dashboard
   payload with `live.resolved_count = 5`, `brier_provisional = true`; assert
   the view model marks the headline Brier AND `firstIndependentBrier` rows
   provisional.
2. `calibration provisional when independent < 150` — payload with
   `calibration_provisional = true`; assert the calibration section is flagged.
3. `empty state when no forecasts` — payload with `resolved_count = 0`,
   `unresolved_count = 0`, empty `calibration`/`brier_trend` arrays; assert the
   view model returns its empty-state shape (whatever the existing function
   returns for empties — assert explicitly, e.g. values render `"—"` and no
   trend points) and that `time_weighted_brier: null` renders `"—"`.

**Gate:** `cd frontend && npm run test -- src/lib/forecast-dashboard-view-model.test.ts`

---

### Task 12 — Safety tests: banned copy, no credential fields, paper-only intact

**Create:** `frontend/src/lib/mirror-copy-safety.test.ts`
**Modify:** `backend/tests/test_config.py`

Frontend test (vitest, node environment — read files with `node:fs`):

```ts
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const BANNED = [
  "place bet",
  "auto bet",
  "guaranteed profit",
  "wallet",
  "private key",
  "real-money",
];

const FILES = [
  "src/app/mirror/page.tsx",
  "src/app/forecast/page.tsx",
  "src/lib/forecast-mirror-api.ts",
  "src/lib/forecast-dashboard-view-model.ts",
];

describe("mirror UI copy safety", () => {
  for (const file of FILES) {
    it(`${file} contains no betting-execution copy or credential fields`, () => {
      const source = readFileSync(path.resolve(__dirname, "../..", file), "utf8").toLowerCase();
      for (const phrase of BANNED) {
        expect(source.includes(phrase), `banned phrase "${phrase}" in ${file}`).toBe(false);
      }
      expect(source.includes('type="password"')).toBe(false);
      expect(source.includes("privatekey")).toBe(false);
    });
  }
});
```

(If a scanned file legitimately contains a banned word today, fix the copy in
that file — do not weaken the test.)

Backend — append to `backend/tests/test_config.py`:

```python
def test_paper_trading_only_cannot_be_disabled():
    with pytest.raises(ValidationError, match="PAPER_TRADING_ONLY"):
        Settings(PAPER_TRADING_ONLY=False)
```

**Gate:** `cd frontend && npm run test -- src/lib/mirror-copy-safety.test.ts` then `cd backend && uv run --extra dev pytest -q tests/test_config.py`

---

### Task 13 — Extension: drop FanDuel; permissions only Polymarket/Kalshi/API

**Modify:** `extension/public/manifest.json`, `extension/src/platforms.ts`,
`extension/src/manifest-safety.test.ts` (and `extension/src/platforms.test.ts` if it
asserts FanDuel parsing)

1. `manifest.json`: remove `"https://sportsbook.fanduel.com/*"` from BOTH
   `host_permissions` and `content_scripts[0].matches`. Keep polymarket.com,
   kalshi.com (and subdomain variants) plus the AlphaEdge API origins
   (`http://localhost:8000/*`, `https://*.alphaedge.local/*`,
   `https://*.azurestaticapps.net/*`, `https://*.vercel.app/*`) exactly as-is.
2. `src/platforms.ts`: remove any FanDuel host/URL detection branch so FanDuel
   pages are not recognized; update `platforms.test.ts` to assert a FanDuel URL
   returns the module's "unrecognized" result.
3. `manifest-safety.test.ts`: add assertions that (a) no entry in
   `host_permissions` or `content_scripts[*].matches` contains `fanduel`, and
   (b) `permissions` is exactly `["storage"]`.

**Gate:** `cd extension && npm run test`

---

### Task 14 — Extension capture card verification + build

**Modify (only if assertions below fail):** `extension/src/content/overlay.tsx`
**Modify:** `extension/src/content/fixture-e2e.test.tsx`

The Shadow DOM capture card already exists (`overlay-host.ts` creates the
shadow root; `overlay.tsx` renders the card; `backend-client.ts` posts to
`POST /api/v1/forecasts` with the `Idempotency-Key` header; `background.ts` is
the MV3 service worker; `popup/Popup.tsx` is the popup). Verify by test, fixing
`overlay.tsx` only if an assertion fails:

Append to `fixture-e2e.test.tsx` (reuse its existing jsdom + fixture setup):

1. `capture card exposes a probability slider and a Lock forecast button` —
   render the overlay against a Polymarket fixture page; assert an
   `input[type="range"]` (or the slider role the component uses — check
   `overlay.tsx` first and match reality) exists, and a button whose text
   matches `/lock forecast/i` exists.
2. `capture card contains no banned execution copy` — assert the rendered
   shadow DOM text content (lowercased) contains none of: `place bet`,
   `auto bet`, `guaranteed profit`, `wallet`, `private key`, `real-money`.

Then run the full extension verification including the production build.

**Gate:** `cd extension && npm run typecheck && npm run test && npm run build`

---

### Task 15 — Full gates, goal bookkeeping, PR + AutoLab lines

**Modify:** `goals/README.md`

1. Run the full final gate (all must pass):

```text
cd backend && uv run --extra dev pytest -q && uv run --extra dev ruff check app tests
cd frontend && npm run typecheck && npm run lint && npm run build
cd extension && npm run typecheck && npm run test && npm run build
```

2. In `goals/README.md`, add one row to the Queue table (above the DEFERRED
   row), matching the table's existing format:

```text
| X | [Mirror MVP close-out](loop-x-mirror-mvp.md) | ✅ DONE | 3, 6 | backend-feature + ui-feature | path scores + /mirror route + FanDuel deferred + safety tests; all gates green |
```

   (Mark `✅ DONE` only after step 1 passes; otherwise leave `🟢 ACTIVE`.)
3. Record the PR line and AutoLab line below in the PR description / handoff.

**Gate:** the full three-command gate in step 1 (every command exit code 0).

---

## Full gate (must pass before claiming the loop)

```text
cd backend && uv run --extra dev pytest -q && uv run --extra dev ruff check app tests
cd frontend && npm run typecheck && npm run lint && npm run build
```

(plus `cd extension && npm run typecheck && npm run test && npm run build` for
the extension tasks.)

## PR line

```text
feat(mirror): MVP close-out — path scores, /mirror route, FanDuel deferred, safety tests | gate=backend pytest+ruff green, frontend typecheck+lint+build green, extension typecheck+test+build green | safety=paper-only,no-exec,append-only: ok
```

## AutoLab handoff line (template — fill measured values)

```text
AutoLab: baseline=<Task 1 counts: backend NNN passed, frontend green, extension NNN passed> | benchmark=full gate (backend pytest+ruff; frontend typecheck/lint/build; extension typecheck/test/build) | iterations=<n; best=all gates green + M new tests> | budget=<used/15 tasks> | outcome=<improved / stalled-reorganized / retired>
```
