"""Plan 003 — ``LivePriceTickService`` extracted from the worker.

The live-price tick loop previously lived as a monolithic function
(``run_live_tick_once``) in ``app/workers/price_feed_worker.py``.  Plan 003
moves the orchestration into a service class so it can be tested and reused
independently of the worker process, while the worker function stays as a
thin wrapper (keeping every existing caller and monkeypatch target working).

Paper-only — refreshes prices for open live markets and publishes ticks to the
websocket hub.  Never touches ``OrderBookService``/``RiskService``.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.data.connectors.kalshi import KalshiConnector, normalize_kalshi_market
from app.data.connectors.kalshi_fetcher import SharedKalshiFetcher
from app.data.connectors.polymarket import PolymarketGammaConnector
from app.db.models import Market, MarketStatus, OddsSnapshot, OrderOutcome
from app.services.market_service import MarketService

logger = logging.getLogger(__name__)

_LIVE_FETCH_CONCURRENCY = 4
_KALSHI_EVENT_CONCURRENCY = 2

# Loop V37 H1 — per-slug 404 backoff for delisted venue slugs. After N
# consecutive 404s, demote via V34 lifecycle lock (or skip with one structured
# warning per hour if lock is unavailable). Non-404 errors always log.
_LIVE_TICK_404_THRESHOLD = 3
_LIVE_TICK_404_WARN_INTERVAL_SEC = 3600.0

# Injectable clock for tests (wall-clock independence of the 1h warn throttle).
_monotonic = time.monotonic


@dataclass
class _Slug404State:
    consecutive: int = 0
    demoted: bool = False
    last_warn_mono: float = 0.0


_slug_404_states: dict[str, _Slug404State] = {}


def reset_live_tick_404_backoff() -> None:
    """Test helper — clear per-slug 404 demotion state."""
    _slug_404_states.clear()


def _http_status(error: BaseException) -> int | None:
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code
    return None


def _warn_throttled(state: _Slug404State, msg: str, *args: object, **extra: object) -> None:
    """Emit at most one structured warning per hour for a demoted slug."""
    now = _monotonic()
    if now - state.last_warn_mono < _LIVE_TICK_404_WARN_INTERVAL_SEC:
        return
    state.last_warn_mono = now
    logger.warning(msg, *args, extra={"event": "live_tick_404_backoff", **extra})


def _clear_slug_404(slug: str) -> None:
    _slug_404_states.pop(slug, None)


def _note_slug_success(slug: str) -> None:
    """Successful tick clears 404 demotion bookkeeping."""
    _clear_slug_404(slug)


def _note_slug_non_404_error(slug: str) -> None:
    """Non-404 failures must not accumulate toward delist demotion."""
    state = _slug_404_states.get(slug)
    if state is not None and not state.demoted:
        state.consecutive = 0


async def latest_implied_yes_by_slug(
    db: AsyncSession, slugs: list[str]
) -> dict[str, float]:
    """Latest ``implied_yes`` per slug in ONE query (window function).

    COST-01: replaces the per-market previous-price SELECT inside
    ``persist_and_publish_tick`` for the batch tick pass. A slug with no
    snapshot rows is simply absent from the result (``.get`` → None keeps the
    'first tick' semantics).
    """
    if not slugs:
        return {}
    ranked = (
        select(
            OddsSnapshot.market_slug,
            OddsSnapshot.implied_yes,
            func.row_number()
            .over(
                partition_by=OddsSnapshot.market_slug,
                order_by=OddsSnapshot.captured_at.desc(),
            )
            .label("rn"),
        )
        .where(OddsSnapshot.market_slug.in_(slugs))
        .subquery()
    )
    rows = (
        await db.execute(
            select(ranked.c.market_slug, ranked.c.implied_yes).where(ranked.c.rn == 1)
        )
    ).all()
    return {slug: float(implied) for slug, implied in rows}


def _terminal_outcome(yes: float) -> OrderOutcome | None:
    if yes >= 0.99:
        return OrderOutcome.YES
    if yes <= 0.01:
        return OrderOutcome.NO
    return None


async def _apply_terminal_state(
    db: AsyncSession,
    market_id,
    slug: str,
    outcome: OrderOutcome | None,
) -> None:
    """Lock a closed live market; resolve + settle when the winner is known."""
    service = MarketService(db)
    try:
        if outcome is not None:
            await service.resolve_market(market_id, outcome)
            logger.info("Live market %s resolved as %s", slug, outcome.value)
        else:
            await service.lock_market(market_id)
            logger.info("Live market %s locked (closed upstream)", slug)
    except ValueError as error:
        logger.warning("Terminal state for %s skipped: %s", slug, error)


class LivePriceTickService:
    """Refresh prices for every open live (Polymarket/Kalshi-mirrored) market.

    Publishes every tick to the websocket hub; persists a snapshot row only
    when the price actually moved (via the shared ``persist_and_publish_tick``
    helper), so charts are real without flooding the DB.
    """

    def __init__(
        self,
        db: AsyncSession,
        *,
        poly_connector_cls: type = PolymarketGammaConnector,
        kalshi_connector_cls: type = KalshiConnector,
    ) -> None:
        self.db = db
        self._poly_cls = poly_connector_cls
        self._kalshi_cls = kalshi_connector_cls

    async def _handle_fetch_error(
        self,
        *,
        slug: str,
        market_id,
        error: BaseException,
        results: dict[str, str],
    ) -> None:
        """Classify per-slug fetch failures; 404s demote after N consecutive hits."""
        status = _http_status(error)
        if status != 404:
            # Never swallow non-404 errors — always surface them.
            _note_slug_non_404_error(slug)
            logger.warning("Live tick fetch failed for %s: %s", slug, error)
            results[slug] = "error"
            return

        state = _slug_404_states.setdefault(slug, _Slug404State())
        if state.demoted:
            _warn_throttled(
                state,
                "Live tick 404 demoted skip for %s (delisted venue slug)",
                slug,
                slug=slug,
                consecutive_404s=state.consecutive,
            )
            results[slug] = "404-demoted-skip"
            return

        state.consecutive += 1
        if state.consecutive < _LIVE_TICK_404_THRESHOLD:
            logger.warning(
                "Live tick fetch failed for %s: %s",
                slug,
                error,
                extra={
                    "event": "live_tick_404",
                    "slug": slug,
                    "consecutive_404s": state.consecutive,
                    "threshold": _LIVE_TICK_404_THRESHOLD,
                },
            )
            results[slug] = "error"
            return

        # N consecutive 404s → V34 lifecycle lock (delisted/missing upstream).
        state.demoted = True
        try:
            await _apply_terminal_state(self.db, market_id, slug, outcome=None)
            _warn_throttled(
                state,
                "Live tick 404 demoted to lifecycle-lock for %s after %d consecutive 404s",
                slug,
                state.consecutive,
                slug=slug,
                consecutive_404s=state.consecutive,
            )
            results[slug] = "404-lifecycle-locked"
        except Exception as lock_error:  # noqa: BLE001 — still demote in-memory
            _warn_throttled(
                state,
                "Live tick 404 demoted-skip for %s (lock failed: %s)",
                slug,
                lock_error,
                slug=slug,
                consecutive_404s=state.consecutive,
            )
            results[slug] = "404-demoted-skip"

    async def run_once(self) -> dict[str, str]:
        from app.workers.price_feed_worker import persist_and_publish_tick

        results: dict[str, str] = {}
        rows = (
            await self.db.execute(
                select(
                    Market.id,
                    Market.slug,
                    Market.external_slug,
                    Market.source,
                    Market.external_id,
                ).where(
                    Market.source.in_(("polymarket", "kalshi")),
                    Market.status == MarketStatus.OPEN,
                    Market.external_slug.is_not(None),
                )
            )
        ).all()
        if not rows:
            return results
        market_ids = {slug: market_id for market_id, slug, _, _, _ in rows}

        settings = get_settings()
        poly_rows = [row for row in rows if row[3] == "polymarket"]
        kalshi_rows = [row for row in rows if row[3] == "kalshi"]

        # H1: skip in-memory-demoted slugs so we don't re-hit delisted venues
        # every tick when lock failed or the row is still OPEN for a race.
        poly_fetch_rows: list = []
        for row in poly_rows:
            slug = row[1]
            state = _slug_404_states.get(slug)
            if state is not None and state.demoted:
                _warn_throttled(
                    state,
                    "Live tick 404 demoted skip for %s (delisted venue slug)",
                    slug,
                    slug=slug,
                    consecutive_404s=state.consecutive,
                )
                results[slug] = "404-demoted-skip"
                continue
            poly_fetch_rows.append(row)

        poly_connector = self._poly_cls()
        semaphore = asyncio.Semaphore(_LIVE_FETCH_CONCURRENCY)
        # Only stand up the Kalshi connector when this tick actually has Kalshi
        # markets — a poly-only tick shouldn't build a client it never calls.
        kalshi_fetcher: SharedKalshiFetcher | None = None
        if kalshi_rows:
            kalshi_connector = self._kalshi_cls(base_url=settings.kalshi_api_base_url)
            kalshi_fetcher = SharedKalshiFetcher(kalshi_connector)
        kalshi_semaphore = asyncio.Semaphore(_KALSHI_EVENT_CONCURRENCY)

        async def fetch_poly(slug: str, external_slug: str):
            async with semaphore:
                try:
                    snapshot = await asyncio.to_thread(
                        poly_connector.fetch_market_snapshot, external_slug
                    )
                    return slug, snapshot, None
                except Exception as error:  # noqa: BLE001 - per-market isolation
                    return slug, None, error

        async def fetch_kalshi_board(
            members: list[tuple[str, str]],
        ) -> list[tuple[str, object | None, Exception | None]]:
            """One batched /markets?tickers=... sweep for the whole Kalshi board
            (plan 004: routed through the shared fetcher for 429 backoff)."""
            tickers = [external_slug for _, external_slug in members]
            try:
                async with kalshi_semaphore:
                    payloads = await asyncio.to_thread(
                        kalshi_fetcher.list_markets_by_tickers, tickers
                    )
            except Exception as error:  # noqa: BLE001
                return [(slug, None, error) for slug, _ in members]

            by_ticker = {
                str(payload.get("ticker") or ""): payload
                for payload in payloads
                if isinstance(payload, dict)
            }
            out: list[tuple[str, object | None, Exception | None]] = []
            for slug, external_slug in members:
                payload = by_ticker.get(external_slug)
                if payload is None:
                    # Absent from the open-markets response → closed/settled upstream;
                    # handled by the lapse sweep, not an error worth logging every tick.
                    out.append((slug, None, None))
                    continue
                try:
                    snapshot = normalize_kalshi_market(payload)
                    out.append((slug, snapshot, None))
                except Exception as error:  # noqa: BLE001
                    out.append((slug, None, error))
            return out

        fetched: list[tuple[str, object | None, Exception | None]] = []
        fetched.extend(
            await asyncio.gather(
                *(
                    fetch_poly(slug, external)
                    for _, slug, external, _, _ in poly_fetch_rows
                )
            )
        )
        if kalshi_rows:
            fetched.extend(
                await fetch_kalshi_board(
                    [(slug, external) for _, slug, external, _, _ in kalshi_rows]
                )
            )

        # COST-01: one batched previous-price query for the whole board instead
        # of one SELECT per market inside persist_and_publish_tick — the N+1
        # round-trips to the managed Postgres were the dominant tick-pass cost.
        prev_by_slug = await latest_implied_yes_by_slug(
            self.db,
            [slug for slug, snapshot, _ in fetched if snapshot is not None],
        )

        for slug, snapshot, error in fetched:
            if snapshot is None:
                if error is not None:
                    await self._handle_fetch_error(
                        slug=slug,
                        market_id=market_ids[slug],
                        error=error,
                        results=results,
                    )
                else:
                    # Absent from the open board ⇒ closed/settled upstream.
                    # Lock only (never resolve here — resolution needs a known
                    # winner; V34 data-quality / V16 V5 lifecycle hygiene).
                    await _apply_terminal_state(
                        self.db, market_ids[slug], slug, outcome=None
                    )
                    _note_slug_success(slug)
                    results[slug] = "missing-upstream-locked"
                continue

            _note_slug_success(slug)
            moved = await persist_and_publish_tick(
                self.db,
                slug=slug,
                yes=float(snapshot.implied_yes),
                source=f"{snapshot.source}-live",
                book=snapshot.book or snapshot.source,
                platform_market_id=snapshot.platform_market_id,
                title=snapshot.title,
                prev_yes=prev_by_slug.get(slug),
            )
            results[slug] = "ok" if moved else "unchanged"

            # Keep the T03/T04 signal pipeline alive on the REST fallback too — not
            # just the WebSocket path. Isolated so a signal failure never drops a tick.
            try:
                from app.data.streams.runner import run_price_signal_pipeline

                await run_price_signal_pipeline(
                    slug, source=snapshot.source, implied_yes=float(snapshot.implied_yes)
                )
            except Exception:  # noqa: BLE001 - signals must not break tick persistence
                logger.warning("Signal pipeline failed for %s", slug, exc_info=True)

            external_status = (snapshot.metadata or {}).get("status")
            if external_status in {"resolved", "closed"}:
                yes = round(float(snapshot.implied_yes), 4)
                outcome = _terminal_outcome(yes) if external_status == "resolved" else None
                await _apply_terminal_state(self.db, market_ids[slug], slug, outcome)
                results[slug] = f"live-{external_status}"

        await self.db.flush()
        return results
