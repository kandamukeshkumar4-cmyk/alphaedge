---
id: loop-y-sell-close
phase: loop-y
status: DONE
depends_on: [loop-x-mirror-mvp]
workflow: backend-feature + ui-feature
executor: Composer 2.5 (low-reasoning — follow tasks literally, in order, one at a time)
---

# Loop Y — True sell/close position lifecycle (paper trading, realized P&L)

> **EXECUTOR PROTOCOL (read first):** Execute Tasks 1–14 strictly in order. Do not
> skip, reorder, or merge tasks. After each task, run that task's **Gate** command
> and do not continue until it passes. If a gate fails, fix only the files named in
> that task. Never edit files outside the lists given per task.

## Why now

Loop W shipped the live trading panel, but "Close position" is a hack: the
frontend (`frontend/src/components/PositionCard.tsx` `closePosition()`) **buys
the opposite outcome** at the current price. That doubles capital locked,
creates a second open position row instead of flattening the first, never
realizes P&L until market resolution, and corrupts portfolio stats. A polished
Polymarket-like product needs a real sell: shares decrease, paper balance is
credited with proceeds, and P&L is realized at sale time. This was the named
follow-up from Loop W.

## Repo reality (verified — do not recreate)

- `PaperOrder` model: `backend/app/db/models.py` lines ~85–100. Columns:
  `id, user_id, slug, side (String(3), stores "YES"/"NO"), outcome (String(3),
  "yes"/"no"), shares, price, cost (Numeric(18,4)), settled (bool),
  created_at`. There is **no buy/sell distinction** today — every row is a buy.
- Buy endpoint + history: `backend/app/api/v1/orders.py`
  (`POST /api/v1/orders`, `GET /api/v1/orders/history`), schemas in
  `backend/app/schemas/orders.py` (`PaperOrderCreate` with legacy-side
  normalizer, `PaperOrderResponse`, `PaperOrderHistoryItem`).
- Portfolio aggregation: `backend/app/api/v1/portfolio.py`
  `_load_paper_orders` is a raw-SQL `GROUP BY po.slug, po.side, po.outcome`
  that sums all rows as buys; realized P&L only comes from settlement
  (`market_resolutions` join). `GET /api/v1/portfolio` and
  `GET /api/v1/portfolio/summary` both call it.
- Resolution lookup: `MarketResolution` model (`backend/app/db/models.py`
  lines ~103–109, table `market_resolutions`, unique `slug`).
- Frontend: `frontend/src/lib/orders-api.ts` (`placePaperOrder`),
  `frontend/src/lib/portfolio-api.ts` (`fetchPortfolio` maps backend
  `shares/avg_cost` → frontend `quantity/price`),
  `frontend/src/components/PositionCard.tsx` (opposite-buy hack),
  `frontend/src/components/MarketTradingPanel.tsx` (renders PositionCard),
  `frontend/src/components/PortfolioBanner.tsx`.
- Tests to copy patterns from: `backend/tests/test_orders.py` and
  `backend/tests/test_order_outcome.py` (`_override_db`, `_signup_token`,
  `MarketService(db_session).seed_catalog_markets()`, canonical slug
  `nba-2025-01-15-lal-bos`); frontend vitest exists (`npm run test`),
  e.g. `frontend/src/components/component-smoke.test.tsx`.
- Latest alembic migration is `020_mirror_dashboard_indexes.py`; **new
  migrations start at 021**.
- The CLOB path (`Order`, `Position`, `OrderBookService`, `RiskService`,
  `settlement_service.py`) is a separate system. **This loop only touches the
  `paper_orders` retail path. Do not modify the CLOB/risk files.**

## Hard guardrails (non-negotiable)

- `PAPER_TRADING_ONLY=true` stays required; do not touch
  `must_be_paper_only` in `backend/app/core/config.py`.
- Do not modify `backend/app/risk/`, `backend/app/services/order_book_service.py`,
  `backend/app/services/settlement_service.py`, `OrderIntent`, or any CLOB code.
- Selling is capped at currently held shares — **no short selling, ever**
  (net shares can never go negative).
- Banned copy in any new UI text: "place bet", "auto bet", "guaranteed
  profit", "wallet", "private key", "real-money".

---

## Tasks (execute strictly in order)

### Task 1 — Record the green baseline

**Modify:** nothing. **Create:** nothing.

From the repo root `E:\polymarket clone`, run and record passing counts (reused
in the Task 14 PR line):

1. `cd backend && uv run --extra dev pytest -q && uv run --extra dev ruff check app tests`
2. `cd frontend && npm run typecheck && npm run lint && npm run test`

**Gate:** `cd backend && uv run --extra dev pytest -q` (exit 0; note `NNN passed`).

---

### Task 2 — Migration 021: `action` + `realized_pnl` on `paper_orders`

**Create:** `backend/alembic/versions/021_paper_order_sell_close.py`
**Modify:** `backend/app/db/models.py`

New migration (follow the exact style of `014_paper_order_outcome.py`):

```python
"""paper_orders sell/close columns

Revision ID: 021_paper_order_sell_close
Revises: 020_mirror_dashboard_indexes
Create Date: 2026-06-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "021_paper_order_sell_close"
down_revision: Union[str, Sequence[str], None] = "020_mirror_dashboard_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "paper_orders",
        sa.Column("action", sa.String(length=4), nullable=False, server_default="BUY"),
    )
    op.add_column(
        "paper_orders",
        sa.Column("realized_pnl", sa.Numeric(18, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("paper_orders", "realized_pnl")
    op.drop_column("paper_orders", "action")
```

In `backend/app/db/models.py`, inside `class PaperOrder` directly below the
`cost` column, add (changing nothing else):

```python
    action: Mapped[str] = mapped_column(String(4), nullable=False, default="BUY", server_default="BUY")
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
```

**Gate:** `cd backend && uv run alembic heads && uv run --extra dev pytest -q tests/test_orders.py tests/test_order_outcome.py`
(heads prints `021_paper_order_sell_close (head)`; tests pass.)

---

### Task 3 — Schemas: close request/response + history fields

**Modify:** `backend/app/schemas/orders.py`

1. Below `PaperOrderResponse`, add:

```python
class PositionCloseRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=128)
    outcome: Literal["yes", "no"]
    shares: float = Field(gt=0)
    price: float = Field(ge=0.01, le=0.99)


class PositionCloseResponse(BaseModel):
    order_id: UUID
    slug: str
    outcome: Literal["yes", "no"]
    shares_sold: float
    proceeds: float
    realized_pnl: float
    remaining_shares: float
    remaining_balance: float
    paper_trading_only: bool = True
```

2. In `PaperOrderHistoryItem`, after `cost: float`, add:

```python
    action: str = "BUY"
    realized_pnl: float | None = None
```

Change nothing else in this file.

**Gate:** `cd backend && uv run --extra dev pytest -q tests/test_orders.py && uv run --extra dev ruff check app`

---

### Task 4 — Position aggregation service (net shares + avg cost)

**Create:** `backend/app/services/paper_position_service.py`

```python
"""Aggregate a user's open paper position for one market outcome.

BUY rows add shares; SELL rows subtract. Average cost is computed from BUY
rows only (sells realize P&L against that average, they do not change it).
"""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PaperOrder


@dataclass(frozen=True)
class OpenPaperPosition:
    net_shares: Decimal
    avg_cost: Decimal  # Decimal("0") when no BUY rows exist


async def get_open_paper_position(
    db: AsyncSession,
    user_id: UUID,
    slug: str,
    outcome: str,
) -> OpenPaperPosition:
    row = (
        await db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (PaperOrder.action == "SELL", -PaperOrder.shares),
                            else_=PaperOrder.shares,
                        )
                    ),
                    0,
                ).label("net_shares"),
                func.coalesce(
                    func.sum(
                        case((PaperOrder.action == "BUY", PaperOrder.cost), else_=0)
                    ),
                    0,
                ).label("buy_cost"),
                func.coalesce(
                    func.sum(
                        case((PaperOrder.action == "BUY", PaperOrder.shares), else_=0)
                    ),
                    0,
                ).label("buy_shares"),
            ).where(
                PaperOrder.user_id == user_id,
                PaperOrder.slug == slug,
                PaperOrder.outcome == outcome,
                PaperOrder.settled.is_(False),
            )
        )
    ).one()
    net_shares = Decimal(str(row.net_shares))
    buy_shares = Decimal(str(row.buy_shares))
    avg_cost = (
        Decimal(str(row.buy_cost)) / buy_shares if buy_shares > 0 else Decimal("0")
    )
    return OpenPaperPosition(net_shares=net_shares, avg_cost=avg_cost)
```

**Gate:** `cd backend && uv run --extra dev ruff check app && uv run --extra dev python -c "import app.services.paper_position_service"`

---

### Task 5 — `POST /api/v1/positions/close` endpoint

**Modify:** `backend/app/api/v1/orders.py`

1. Add to the imports: `MarketResolution` from `app.db.models`;
   `PositionCloseRequest, PositionCloseResponse` from `app.schemas.orders`;
   `from app.services.paper_position_service import get_open_paper_position`.
2. Append this endpoint at the bottom of the file:

```python
@router.post(
    "/positions/close",
    response_model=PositionCloseResponse,
    status_code=status.HTTP_200_OK,
)
async def close_paper_position(
    body: PositionCloseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PositionCloseResponse:
    if not settings.paper_trading_only:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PAPER_TRADING_ONLY must be true",
        )

    market = await db.scalar(select(Market).where(Market.slug == body.slug))
    if market is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid market slug")

    resolution = await db.scalar(
        select(MarketResolution).where(MarketResolution.slug == body.slug)
    )
    if resolution is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Market already resolved; positions settle automatically",
        )

    position = await get_open_paper_position(db, current_user.id, body.slug, body.outcome)
    shares = Decimal(str(body.shares))
    if shares > position.net_shares:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot sell more shares than held",
        )

    price = Decimal(str(body.price))
    proceeds = shares * price
    realized = shares * (price - position.avg_cost)

    current_user.paper_balance += proceeds
    order = PaperOrder(
        user_id=current_user.id,
        slug=body.slug,
        side=body.outcome.upper(),
        outcome=body.outcome,
        shares=shares,
        price=price,
        cost=proceeds,
        action="SELL",
        realized_pnl=realized,
    )
    db.add(order)
    await db.flush()

    return PositionCloseResponse(
        order_id=order.id,
        slug=body.slug,
        outcome=body.outcome,
        shares_sold=float(shares),
        proceeds=round(float(proceeds), 4),
        realized_pnl=round(float(realized), 4),
        remaining_shares=float(position.net_shares - shares),
        remaining_balance=float(current_user.paper_balance),
        paper_trading_only=True,
    )
```

**Gate:** `cd backend && uv run --extra dev pytest -q tests/test_orders.py && uv run --extra dev ruff check app`

---

### Task 6 — BUY path: explicit action + reject resolved markets

**Modify:** `backend/app/api/v1/orders.py`

In `place_paper_order`:

1. After the `market is None` check, add the same resolved-market guard as
   Task 5 (query `MarketResolution` by `body.slug`; if found, raise 409 with
   detail `"Market already resolved"`).
2. In the `PaperOrder(...)` constructor, add `action="BUY",` after `cost=cost,`.

**Gate:** `cd backend && uv run --extra dev pytest -q tests/test_orders.py tests/test_order_outcome.py`

---

### Task 7 — Portfolio aggregation: net shares + realized P&L from sells

**Modify:** `backend/app/api/v1/portfolio.py`

Replace the SQL inside `_load_paper_orders` (keep the function signature,
mapping loop, and `PortfolioPositionResponse` construction; only the query text
and one post-filter change):

```sql
SELECT po.slug, po.side, po.outcome,
       COALESCE(m.title, po.slug) AS market_title,
       SUM(CASE WHEN po.action='SELL' THEN -po.shares ELSE po.shares END) AS shares,
       CASE WHEN SUM(CASE WHEN po.action='BUY' THEN po.shares ELSE 0 END) > 0
            THEN SUM(CASE WHEN po.action='BUY' THEN po.cost ELSE 0 END)
                 / SUM(CASE WHEN po.action='BUY' THEN po.shares ELSE 0 END)
            ELSE 0 END                                                    AS avg_cost,
       SUM(CASE WHEN po.action='SELL' THEN -po.cost ELSE po.cost END)     AS cost,
       MAX(CASE WHEN po.settled THEN 1 ELSE 0 END) AS settled,
       SUM(COALESCE(po.realized_pnl, 0.0)) +
       SUM(
         CASE WHEN po.settled AND po.action='BUY' AND UPPER(po.outcome)=COALESCE(mr.outcome,'')
              THEN po.shares*1.0 - po.cost
              WHEN po.settled AND po.action='BUY' THEN 0.0 - po.cost
              ELSE 0.0 END
       ) AS realized_pnl
FROM paper_orders po
LEFT JOIN markets m ON m.slug=po.slug
LEFT JOIN market_resolutions mr ON mr.slug=po.slug
WHERE po.user_id=:user_id
GROUP BY po.slug, po.side, po.outcome
ORDER BY MAX(po.created_at) DESC
```

Then, in the row-mapping loop, before appending each position, skip fully
closed unsettled positions but keep their realized P&L visible in totals:

```python
        shares = float(row["shares"])
        settled = bool(row["settled"])
        if shares <= 0 and not settled:
            # Fully closed via sell: surface as a settled (closed) row so
            # realized P&L still counts in the portfolio totals.
            settled = True
```

and pass `shares=max(shares, 0.0)` and `settled=settled` into
`PortfolioPositionResponse`. Also, where `cost=float(row["cost"])` is set,
clamp with `max(..., 0.0)` so a fully closed position cannot show negative
remaining basis. Change nothing else in this file (the `_enrich_live_pnl`
mark-to-market math stays as-is — it already skips settled rows).

**Gate:** `cd backend && uv run --extra dev pytest -q tests/test_portfolio.py tests/test_portfolio_live_pnl.py tests/test_portfolio_summary.py`

---

### Task 8 — Order history exposes action + realized P&L

**Modify:** `backend/app/api/v1/orders.py`

In `get_order_history`, add to the `PaperOrderHistoryItem(...)` constructor:

```python
            action=order.action,
            realized_pnl=float(order.realized_pnl) if order.realized_pnl is not None else None,
```

**Gate:** `cd backend && uv run --extra dev pytest -q tests/test_orders.py && uv run --extra dev ruff check app`

---

### Task 9 — Backend tests: close lifecycle

**Create:** `backend/tests/test_position_close.py`

Copy the exact fixture pattern from `backend/tests/test_orders.py`
(`_override_db`, `_signup_token`, `MarketService(db_session).seed_catalog_markets()`,
`CANONICAL_SLUG = "nba-2025-01-15-lal-bos"`, `AsyncClient(transport=ASGITransport(app=app), ...)`).
Write these tests:

1. `test_close_requires_auth` — POST `/api/v1/positions/close` with no token → 401.
2. `test_close_rejects_invalid_slug` — valid token, slug `"not-in-catalog"` → 400.
3. `test_close_rejects_when_no_position` — seeded market, no prior buy, sell 5
   shares → 400 `"Cannot sell more shares than held"`.
4. `test_close_full_position_credits_balance_and_realizes_pnl` — buy 10 yes @
   0.40 (balance 100000 → 99996), close 10 @ 0.60 → 200; assert
   `proceeds == 6.0`, `realized_pnl == 2.0` (10 × (0.60 − 0.40)),
   `remaining_shares == 0.0`, `remaining_balance == 100002.0`; then GET
   `/api/v1/auth/me` shows `paper_balance == 100002.0`.
5. `test_partial_close_leaves_remainder` — buy 10 yes @ 0.40, close 4 @ 0.50 →
   `remaining_shares == 6.0`; a second close of 7 shares → 400.
6. `test_close_rejects_resolved_market` — insert a
   `MarketResolution(slug=CANONICAL_SLUG, outcome="YES")` via `db_session`,
   then close → 409.
7. `test_close_writes_sell_order_row` — after a close, `select(PaperOrder)`
   where `action == "SELL"` returns one row with `realized_pnl` set, and GET
   `/api/v1/orders/history` includes an item with `action == "SELL"`.

**Gate:** `cd backend && uv run --extra dev pytest -q tests/test_position_close.py`

---

### Task 10 — Backend tests: portfolio after sells + settlement no-double-pay

**Modify:** `backend/tests/test_position_close.py` (append; same fixtures)

1. `test_portfolio_nets_out_sold_shares` — buy 10 yes @ 0.40, close 4 @ 0.50;
   GET `/api/v1/portfolio` → the position row has `shares == 6.0`,
   `avg_cost == 0.4`, `realized_pnl == pytest.approx(0.4)`; portfolio-level
   `realized_pnl == pytest.approx(0.4)`.
2. `test_fully_closed_position_not_double_paid_on_settlement` — buy 10 yes @
   0.40, close all 10 @ 0.60, then resolve the market YES via the same
   mechanism `backend/tests/test_market_resolution.py` uses (check that file
   first and copy its resolve call exactly — admin endpoint or service);
   assert the user balance gained only the sale proceeds (100002.0), not an
   additional 10.0 settlement payout, and `/api/v1/portfolio` shows the
   position with `shares == 0.0` and `settled == True`.
   If the resolve mechanism pays settled-flag rows regardless of action, the
   fix belongs in the resolution code path for `paper_orders` rows: a SELL row
   must never receive a settlement payout, and BUY shares already sold must
   not be paid. Make the minimal fix in the file that pays out `paper_orders`
   (find it via `rg "settled" backend/app --type py` — it is the
   market-resolution service/endpoint, NOT `settlement_service.py` which is
   CLOB-only and must stay untouched).
3. `test_portfolio_summary_excludes_closed_positions` — after a full close,
   GET `/api/v1/portfolio/summary` → `open_positions == 0`.

**Gate:** `cd backend && uv run --extra dev pytest -q tests/test_position_close.py tests/test_market_resolution.py tests/test_portfolio.py`

---

### Task 11 — Frontend API client: `closePaperPosition`

**Modify:** `frontend/src/lib/orders-api.ts`

Append (mirroring the `placePaperOrder` error-handling style exactly):

```ts
export type PositionCloseInput = {
  slug: string;
  outcome: "yes" | "no";
  shares: number;
  price: number;
};

export type PositionCloseResponse = {
  order_id: string;
  slug: string;
  outcome: "yes" | "no";
  shares_sold: number;
  proceeds: number;
  realized_pnl: number;
  remaining_shares: number;
  remaining_balance: number;
  paper_trading_only: true;
};

export async function closePaperPosition(
  token: string,
  input: PositionCloseInput,
): Promise<PositionCloseResponse> {
  const apiBase = API_BASE || "http://localhost:8000";
  const response = await fetch(`${apiBase}/api/v1/positions/close`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : `Close request failed with HTTP ${response.status}`;
    throw new Error(detail);
  }

  return (await response.json()) as PositionCloseResponse;
}
```

**Gate:** `cd frontend && npm run typecheck && npm run lint`

---

### Task 12 — PositionCard: real sell instead of opposite-buy

**Modify:** `frontend/src/components/PositionCard.tsx`

1. Replace the `placePaperOrder` import with
   `import { closePaperPosition } from "@/lib/orders-api";`.
2. Replace the body of `closePosition()`:

```ts
  async function closePosition() {
    setClosing(true);
    try {
      const result = await closePaperPosition(token, {
        slug: position.market_slug,
        outcome: position.outcome.toLowerCase() === "yes" ? "yes" : "no",
        shares: position.shares,
        price: Math.min(Math.max(currentPrice, 0.01), 0.99),
      });
      const pnlText = `${result.realized_pnl >= 0 ? "+" : ""}$${result.realized_pnl.toFixed(2)}`;
      toast({ title: "Position closed", body: `Realized P&L ${pnlText}`, tone: "success" });
      onClosed?.();
    } catch (err) {
      toast({
        title: "Close failed",
        body: err instanceof Error ? err.message : "Unable to close position",
        tone: "error",
      });
    } finally {
      setClosing(false);
    }
  }
```

3. Update the button label so it no longer says "Buy NO/YES":

```ts
        {closing ? "Closing…" : `Sell ${position.shares.toFixed(0)} shares (${fmtUSD(position.shares * currentPrice)})`}
```

**Gate:** `cd frontend && npm run typecheck && npm run lint`

---

### Task 13 — Frontend tests: close payload + copy safety

**Create:** `frontend/src/lib/orders-close.test.ts`

Vitest, node environment. Stub `global.fetch` with `vi.fn()`:

1. `closePaperPosition posts to /api/v1/positions/close with bearer token` —
   resolve fetch with `{ ok: true, json: async () => ({ ...minimal valid
   PositionCloseResponse }) }`; assert the URL ends with
   `/api/v1/positions/close`, method is `POST`, the `Authorization` header is
   `Bearer test-token`, and the JSON body round-trips `{ slug, outcome,
   shares, price }`.
2. `closePaperPosition surfaces backend detail on error` — resolve fetch with
   `{ ok: false, status: 400, json: async () => ({ detail: "Cannot sell more
   shares than held" }) }`; assert the thrown error message equals that detail.
3. `position card source contains no banned execution copy` — read
   `frontend/src/components/PositionCard.tsx` with `node:fs` `readFileSync`
   (resolve the path relative to the test file) and assert the lowercased
   source contains none of: `place bet`, `auto bet`, `guaranteed profit`,
   `wallet`, `private key`, `real-money`.

**Gate:** `cd frontend && npm run test -- src/lib/orders-close.test.ts`

---

### Task 14 — Full gates, goal bookkeeping, PR + AutoLab lines

**Modify:** `goals/README.md`

1. Run the full final gate (all must pass):

```text
cd backend && uv run --extra dev pytest -q && uv run --extra dev ruff check app tests
cd frontend && npm run typecheck && npm run lint && npm run test && npm run build
```

2. In `goals/README.md`, set the Loop Y row (added when this ticket was
   queued) to `✅ DONE` with gate text:
   `sell/close endpoint + realized P&L + netted portfolio + no-double-pay settlement; all gates green`.
   (Mark `✅ DONE` only after step 1 passes; otherwise leave `🟢 ACTIVE`.)
3. Record the PR line and AutoLab line below in the PR description / handoff.

**Gate:** the full two-command gate in step 1 (every command exit code 0).

---

## Full gate (must pass before claiming the loop)

```text
cd backend && uv run --extra dev pytest -q && uv run --extra dev ruff check app tests
cd frontend && npm run typecheck && npm run lint && npm run test && npm run build
```

## PR line

```text
feat(trading): true sell/close position lifecycle — POST /positions/close, realized P&L, netted portfolio, settlement no-double-pay | gate=backend pytest+ruff green, frontend typecheck+lint+test+build green | safety=paper-only,no-short-selling,CLOB-path-untouched: ok
```

## AutoLab handoff line

```text
AutoLab: not applicable (feature loop with binary gates, no iterative measure)
```
