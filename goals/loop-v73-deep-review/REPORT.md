# Loop V73 — Deep End-to-End Review

**Scope:** Full codebase risk review (not a diff). Surfaces: `backend/app` (services, workers, pods, signals, ml, api, risk, db), `frontend/src` (spot-checked for dishonest presentation), Alembic migrations, CI workflows.

**Focus only:** data loss/corruption, security exposure, money-math (paper balances/positions/scoring), silent 24/7 loop failure, dishonest data shown as real.

**Explicitly excluded (already known V68–V72 — not re-reported):** heartbeat halt/exit-key/time-stop/bankroll/redaction; pods exposure/seeding/universe/equity/leakage/price-delta; missing retention for whale_events/sentiment_snapshots/decision_logs/pod_trades; unbounded signal caches; AsyncOpenAI leak; news flag-off 12x burn; LOOP_INTERVALS news_scan mismatch; circuit-breaker duplication; bare `create_task` pattern; frontend races/CountUp/NaN/sitemap; migration docstring leftovers.

**Method:** Direct file reads of order/settlement/ledger/risk paths, auth deps, WS + lifespan loops, scoring leakage gates, paper position aggregation, pods runner, admin resolve, retention worker, CI backend workflow. HEAD at review time: `71bfd3b`.

**Finding count:** 10 (cap 12). Ordered by severity.

---

## Findings

### 1. Concurrent CLOB fills can overfill resting liquidity (money creation)

| Field | Value |
| --- | --- |
| **Severity** | **critical** |
| **Likelihood** | Medium under concurrent takers on the same maker (pods + API + multi-worker); low under single-serial load |
| **Impact** | `filled_quantity` can exceed `quantity`; positions and ledger credits/debits apply twice against the same resting size → phantom shares and cash |

**Evidence (read):**

```445:473:backend/app/services/order_book_service.py
            # Audit H-RACE-03: lock the maker+taker rows for the fill so two
            # concurrent takers cannot both advance filled_quantity past
            # quantity against the same resting liquidity.
            result = await self.session.execute(
                select(Order).where(Order.id == order_id).with_for_update()
            )
            order = result.scalar_one()
            await self._apply_fill_to_position(order, match.price, match.quantity)
            self._advance_order_fill_state(order, match.quantity)
        ...
    def _advance_order_fill_state(order: Order, quantity: Decimal) -> None:
        order.filled_quantity += quantity
        if order.filled_quantity >= order.quantity:
            order.status = OrderStatus.FILLED
```

Matching hydrates a **per-request in-memory book** from DB (`_get_hydrated_book`, lines 51–81) with no shared lock across sessions. Two concurrent takers each see the full remaining maker size, both match, both lock and **unconditionally add** fill qty. The comment claims overfill protection; the code never checks `filled_quantity + quantity <= quantity` (or remaining) before applying ledger mutations.

**Smallest viable fix:** Under the existing `FOR UPDATE`, compute `remaining = order.quantity - order.filled_quantity`; if `remaining <= 0`, skip/abort fill; else apply `min(match.quantity, remaining)` only, and reject/adjust the paired leg consistently (or fail the whole fill + roll back). Prefer also matching against DB-authoritative remaining rather than only the in-memory book when concurrent writers exist.

---

### 2. Unauthenticated `/ws/feed` broadcasts private notifications to every subscriber

| Field | Value |
| --- | --- |
| **Severity** | **high** |
| **Likelihood** | High if any client opens the public feed socket (homepage does) |
| **Impact** | Security/privacy exposure: order-fill and follow notifications (title/body/user_id/link) are process-wide; frontend filters client-side only |

**Evidence (read):**

```23:30:backend/app/api/v1/ws.py
_FEED_TOPICS = (
    "briefs",
    "alerts",
    "feed",
    "activity",
    "notifications",
    "forecasts",
)
```

```106:113:backend/app/api/v1/ws.py
    settings = get_settings()
    if not settings.paper_trading_only:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
```

```112:132:backend/app/services/notification_service.py
async def _publish_new_notification(row: Notification) -> None:
    ...
        await hub.publish(
            "notifications",
            {
                "type": "notification",
                "id": str(row.id),
                "user_id": str(row.user_id),
                "notification_type": row.type,
                "title": row.title,
                "body": row.body,
                "link": row.link,
                ...
            },
        )
```

Frontend `notifications-api.ts` drops other users’ frames only after receipt (`user_id` client filter). Any raw WebSocket client receives everyone’s notifications without auth.

**Smallest viable fix:** Stop publishing PII/order content on the shared hub topic. Options (pick one): (a) per-user hub topics keyed by `user_id` + require JWT/cookie on a dedicated notifications WS; (b) publish only a opaque “nudge” (`user_id` + `id`) and force authenticated REST fetch for body; (c) remove `notifications` from `_FEED_TOPICS` and poll authenticated REST only.

---

### 3. Live markets are locked but never auto-resolved → paper/CLOB positions never settle

| Field | Value |
| --- | --- |
| **Severity** | **high** |
| **Likelihood** | High in 24/7 ops: live ingest + `lapse_expired_markets` run; venue resolution for catalog `Market` rows does not |
| **Impact** | Silent integrity failure: after `lock_at`, positions remain open, cash stays in shares, JWT paper never credits settlement; UI can show “live” MTM against stale last ticks |

**Evidence (read):**

```120:147:backend/app/workers/price_feed_worker.py
async def lapse_expired_markets(db: AsyncSession) -> int:
    """Lock any open market whose lock_at has passed.
    ...
    """
    ...
            await service.lock_market(market_id)
```

`lock_market` only flips status to LOCKED. Auto-resolution exists for **external** forecast markets (`resolve_external_markets`) and **WC2026** CLOB (`wc2026_resolver` → `settle_market`), not for general Polymarket-mirrored catalog markets. JWT paper settlement only runs from admin slug resolve (finding 4).

**Smallest viable fix:** Add a venue-resolution worker for open/locked live catalog markets (platform id → terminal outcome) that calls a **single** settlement entrypoint: CLOB `settle_market` + JWT `_settle_paper_orders` + `MarketResolution` row. Until then, surface “locked, unsettled” honestly in portfolio UI and refuse implying terminal PnL.

---

### 4. Dual settlement paths: admin UUID path skips paper + `settled`; paper settle is catalog-only

| Field | Value |
| --- | --- |
| **Severity** | **high** |
| **Likelihood** | Medium (depends which admin endpoint operators use); paper gap is certain for non-catalog slugs |
| **Impact** | Money-math inconsistency: CLOB paid without marking `Position.settled`; JWT `paper_balance` never credited; re-entry of settlement tooling can diverge |

**Evidence (read):**

```221:281:backend/app/services/market_service.py
    async def resolve_market(self, market_id: UUID, winning_outcome: OrderOutcome) -> Market:
        ...
        await self._settle_positions(market)
        ...
    async def _settle_positions(self, market: Market) -> None:
        ...
            if payout > 0:
                await self.ledger.credit(...)
            if liability > 0:
                await self.ledger.debit(...)
            pos.yes_shares = Decimal("0")
            pos.no_shares = Decimal("0")
        # never sets pos.settled = True; no paper orders; no MarketResolution
```

```327:351:backend/app/api/v1/admin_markets.py
    """Resolve a catalog market and settle paper orders ..."""
    if slug not in CATALOG_SLUGS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Market not found")
    ...
    summary = await settle_market(db, slug, winning_outcome)
    paper_orders_settled = await _settle_paper_orders(db, slug, winning_outcome)
    ...
    resolution = MarketResolution(slug=slug, outcome=winning_outcome)
```

`settle_market` (claim CAS + `settled=True`) is the safer CLOB path; `MarketService._settle_positions` is a second incomplete implementation. WC2026 resolver also calls only `settle_market` (no paper).

**Smallest viable fix:** Delete/inline `_settle_positions` in favor of `settle_market`; always write `MarketResolution` + `_settle_paper_orders` for the slug; remove `CATALOG_SLUGS` hard gate (or expand to all resolvable markets). One entrypoint only.

---

### 5. CLOB `RiskService` gates are client-supplied honor system

| Field | Value |
| --- | --- |
| **Severity** | **high** |
| **Likelihood** | High for any caller of `POST /api/v1/markets/{slug}/orders` with a paper account token |
| **Impact** | Edge/confidence/drawdown gates do not constrain real behavior; bankroll % cap still uses server bankroll, but “risk-gated trading” is dishonest as a control |

**Evidence (read):**

```517:534:backend/app/api/v1/routes.py
    intent = OrderIntent(
        ...
        predicted_prob=body.risk.predicted_prob,
        confidence=body.risk.confidence,
        edge=body.risk.edge,
        bankroll=account.cash_balance,
        current_drawdown=body.risk.current_drawdown,
        minutes_before_start=_minutes_before_market_lock(
            market,
            fallback=body.risk.minutes_before_start,
        ),
```

Clients set `edge=0.99`, `confidence=0.99`, `current_drawdown=0` and pass validation. Server only overrides lock timing when `lock_at` is set.

**Smallest viable fix:** For non-exit human/CLOB API path, either (a) recompute edge/confidence from server model prediction + book mid, or (b) drop model gates on this path and document it as cash/position-gated only (like JWT paper). Do not accept client `current_drawdown` — compute from ledger equity curve.

---

### 6. JWT paper avg-cost / close PnL / VOID credit break after full close-and-reopen

| Field | Value |
| --- | --- |
| **Severity** | **high** |
| **Likelihood** | Medium for active paper traders who round-trip the same market |
| **Impact** | Wrong `realized_pnl` on close; wrong VOID refunds at resolve; dishonest portfolio avg cost |

**Evidence (read):**

```41:70:backend/app/services/paper_position_service.py
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
                ...
                PaperOrder.settled.is_(False),
            )
    ...
    open_cost_basis = (
        buy_cost * (net_shares / buy_shares)
        if buy_shares > 0 and net_shares > 0
        else Decimal("0")
    )
```

Unsettled rows include **all** historical BUY/SELL legs until market resolution marks them settled. After buy→full sell→buy again, `buy_shares` still counts the closed cycle, so remaining cost basis is a blend of dead and live fills. Same proportional formula is copied in `_settle_paper_orders` VOID credit (`admin_markets.py` ~97–103) and portfolio SQL (`portfolio.py` ~131–134).

**Smallest viable fix:** Compute open lots with running inventory (or mark closed cycles settled on full exit), so cost basis only uses BUY lots still covering `net_shares`. Prefer FIFO/average-lot table; minimal fix is settle-or-archive closed cycles when net hits 0.

---

### 7. CLOB position average cost is last-fill price, not weighted average

| Field | Value |
| --- | --- |
| **Severity** | **high** |
| **Likelihood** | High whenever an account scales into a position across multiple fills |
| **Impact** | Wrong VOID refunds (`settlement_service._leg_payout` uses `avg_*_cost`); wrong pod MTM at cost (`pods/runner._position_value`); wrong heartbeat entry marks |

**Evidence (read):**

```494:517:backend/app/services/order_book_service.py
                pos.yes_shares += quantity
                if pos.yes_shares > 0:
                    pos.avg_yes_cost = price
            ...
                pos.no_shares += quantity
                if pos.no_shares > 0:
                    pos.avg_no_cost = price
```

Each buy **overwrites** average with the latest fill price.

**Smallest viable fix:** Standard weighted average on buys while long:

`avg = (avg * prev_qty + price * fill_qty) / (prev_qty + fill_qty)` when increasing a long; leave avg unchanged on partial sells; reset when crossing through zero.

---

### 8. Pod entry fees are estimated for caps but never debited from cash

| Field | Value |
| --- | --- |
| **Severity** | **medium** |
| **Likelihood** | Certain whenever pods enter (when `PODS_ENABLED`) |
| **Impact** | Dishonest pod equity: `trade.fee` stored and included in exposure `proposed`, but ledger only pays `price * quantity` on fill |

**Evidence (read):**

```293:340:backend/app/pods/runner.py
    fee = estimate_entry_fee(...)
    ...
    proposed = limit_price * quantity + fee
    if await _open_exposure(session, account.id) + proposed > max_exposure:
        ...
    order = await OrderBookService(...).submit_order(...)
    ...
    trade.fee = fee
```

No `ledger.debit` for fee after fill. Equity snapshots = cash + cost basis of positions (`_snapshot_pod_equity`) without cumulative fees.

**Smallest viable fix:** After successful submit/fill, debit `fee` from the pod account (or bake fee into limit notional and record it), and include cumulative fees in equity. If fees are “display only,” stop adding them to the exposure cap and label them non-cash.

---

### 9. JWT paper settlement credits balances with non-atomic ORM RMW

| Field | Value |
| --- | --- |
| **Severity** | **medium** |
| **Likelihood** | Low (resolve is admin/rare) but severity is balance corruption if concurrent credits hit the same user |
| **Impact** | Lost updates on `User.paper_balance` under concurrency; asymmetric with buy/close atomic `UPDATE ... RETURNING` |

**Evidence (read):**

```112:117:backend/app/api/v1/admin_markets.py
    if winner_credits:
        users = (
            await db.scalars(select(User).where(User.id.in_(list(winner_credits))))
        ).all()
        for user in users:
            user.paper_balance += winner_credits[user.id]
```

Buy path correctly uses atomic `UPDATE` with balance guard (`orders.py` ~241–247); settlement does not.

**Smallest viable fix:** Mirror buy path:

`UPDATE users SET paper_balance = paper_balance + :credit WHERE id = :id RETURNING paper_balance`.

---

### 10. CLOB VOID settlement leaves short positions with free proceeds

| Field | Value |
| --- | --- |
| **Severity** | **medium** |
| **Likelihood** | Low until VOID is used operationally; high impact when it is |
| **Impact** | Short sellers keep sale proceeds; longs get `qty * entry` refund; shorts get liability 0 on VOID → free money |

**Evidence (read):**

```25:53:backend/app/services/settlement_service.py
def _leg_payout(...):
    if quantity <= 0:
        return Decimal("0")
    if winning_outcome == "VOID":
        return quantity * entry_price
    ...
def _leg_liability(...):
    if quantity >= 0:
        return Decimal("0")
    if winning_outcome == "YES" and leg == "YES":
        return -quantity
    if winning_outcome == "NO" and leg == "NO":
        return -quantity
    return Decimal("0")  # VOID shorts fall through here
```

Shorts receive `price * qty` cash at fill (`_apply_fill_to_position` credit). On VOID they need to return that premium (and release `(1-price)` collateral accounting). Code returns liability 0.

**Smallest viable fix:** On VOID, for `quantity < 0`, debit `-quantity * entry_price` (or debit sale proceeds recorded at fill). Align long refund and short clawback so both net to flat.

---

## Unresolved concerns (not counted)

These have concrete basis but could not be fully confirmed end-to-end in this pass:

1. **Multi-process CLOB book divergence** — `OrderBookService._books` is per-process memory; free-tier is single API process, but if workers/API both match, books diverge. *Check next:* deployment topology (API replicas + ARQ workers submitting orders).
2. **`portfolio.py` uses `current_user.id.hex` in raw SQL** (`~196`) — Postgres usually accepts unhyphenated UUIDs; other drivers may not. *Check next:* integration test on production dialect asserting non-empty positions for a known user.
3. **Production secret defaults** — `config.py` defaults `admin_api_key="dev-admin-key"` and a fixed JWT secret. *Check next:* `scripts/verify_prod.py` / deploy env that secrets are overridden (do not log values).
4. **Alembic `015` downgrade deletes seed markets** without cascading child rows (`orders`, `odds_snapshots`, …). *Check next:* dry-run `alembic downgrade` on a DB that has traded those slugs; expect FK failures.
5. **CI branch filter** — `.github/workflows/ci-backend.yml` only triggers on `loop3-agent-memory` / `codex/alphaedge-base`. *Check next:* whether default branch PRs still get backend CI via another workflow or branch rename.
6. **Scoring leakage when `locked_at` is NULL** — gate only skips when `locked_at is not None and locked_at >= resolved_at`. Lock path always sets `locked_at` today; a manual DB row could score. *Check next:* DB constraint `locked_at NOT NULL` for LIVE mode.

---

## What was intentionally not deep-dived

- Full frontend UX beyond dishonest-data signals (paper disclaimers appear present on major surfaces).
- Exhaustive per-route auth matrix for every public GET (most are intentionally public research reads).
- ML training pipelines beyond leakage gate on `ScoringService` / V40 forecast AB helpers (gate present for LIVE).
- Extension/ and loadtest/ trees.

---

## Summary

| # | Severity | One-line |
| --- | --- | --- |
| 1 | critical | Concurrent CLOB fills can overfill and mint phantom positions/cash |
| 2 | high | Public WS leaks private notifications |
| 3 | high | Live markets lock forever without resolution/settlement |
| 4 | high | Two settlement implementations; paper settle catalog-only |
| 5 | high | Risk gates take client edge/confidence/drawdown |
| 6 | high | Paper cost basis wrong after close-and-reopen |
| 7 | high | CLOB avg cost = last fill only |
| 8 | medium | Pod fees not charged to cash |
| 9 | medium | Paper settlement balance not atomic |
| 10 | medium | VOID shorts keep proceeds |

**AutoLab:** not applicable (no iterative measure; review-only).

**Commit scope:** this report only. No code changes. Do not push/merge from this review.

---

## Orchestrator disposition (2026-07-17)

Findings: #1,#2,#7,#6,#10,#9 -> Loop V74 (in flight); #3,#4,#5,#8 + unresolved
#6 -> Loop V75 (queued behind V74, shared files); retention/ops cluster ->
Loop V70 (in flight).

Unresolved concerns closed by direct check:
- #1 multi-process book divergence: prod runs a single uvicorn process, no ARQ
  worker (REDIS_URL=disabled) — books cannot diverge today; revisit if
  replicas are ever added.
- #3 prod secrets: ADMIN_API_KEY and JWT_SECRET_KEY are overridden with real
  values in Railway (verified by name/prefix, values not logged).
- #5 CI branch filter: ci-backend triggers on loop3-agent-memory and
  codex/alphaedge-base — the two branches all work pushes to; CI runs on
  every push. Working as intended.
Still parked: #2 uuid.hex raw-SQL dialect (add prod-dialect integration test
in V75); #4 alembic 015 downgrade FK cascade (downgrade-to-015 is not an
operational path; documented hazard only).
