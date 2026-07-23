"""Wiring that connects market streams to the shared tick persist/publish path.

Kept out of ``main.py`` so the lifespan stays readable and the bridge is testable
in isolation. A stream is long-lived; each event opens a short-lived DB session,
persists (if moved), commits, and closes — we never hold a session for the socket
lifetime.
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.data.streams.base import StreamEvent, StreamEventKind
from app.data.streams.kalshi_ws import KalshiMarketStream
from app.data.streams.polymarket_ws import PolymarketMarketStream
from app.db.models import Market, MarketStatus
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


def background_loop_plan(settings) -> list[str]:
    """Which background loops the app should start, given settings.

    Pure and testable so the degrade-to-polling contract is provable: turning off
    a WS stream must NOT remove the REST polling loops. ``price_feed`` always runs;
    ``live_ingest``/``live_tick`` (REST) run whenever ``live_feed_enabled``; the WS
    streams are additive on top and independently flagged.
    """
    plan = ["price_feed"]
    if getattr(settings, "live_feed_enabled", False):
        plan.extend(["live_ingest", "live_tick"])
        if getattr(settings, "kalshi_ws_enabled", False):
            plan.append("kalshi_ws")
        if getattr(settings, "polymarket_ws_enabled", False):
            plan.append("polymarket_ws")
    return plan


async def kalshi_ticker_slug_map() -> dict[str, str]:
    """Map Kalshi upstream ticker -> local market slug for open mirrored markets."""
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(Market.external_slug, Market.slug).where(
                    Market.source == "kalshi",
                    Market.status == MarketStatus.OPEN,
                    Market.external_slug.is_not(None),
                )
            )
        ).all()
    return {str(ticker): str(slug) for ticker, slug in rows if ticker}


async def polymarket_token_slug_map() -> dict[str, str]:
    """Map Polymarket YES CLOB token id -> local slug for open mirrored markets."""
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(Market.clob_token_id, Market.slug).where(
                    Market.source == "polymarket",
                    Market.status == MarketStatus.OPEN,
                    Market.clob_token_id.is_not(None),
                )
            )
        ).all()
    return {str(token): str(slug) for token, slug in rows if token}


async def run_price_signal_pipeline(slug: str, source: str, implied_yes: float) -> None:
    """Feed one price observation through the diff engine + alignment scorer (T03/T04).

    Shared by the WebSocket stream path (`_run_diff_engine`) and the REST poll
    fallback (`run_live_tick_once`) so BOTH keep the signal pipeline alive — not
    just tick persistence. Previously only the WS path fed the diff engine, so
    whenever the streams were down (rate-limited, unsubscribed) every delta,
    alignment trigger, brief and claim was silently dropped while ticks kept
    persisting. Keyed by slug in-memory, so calling from both paths is safe.
    """
    from app.core.config import get_settings
    from app.signals.diff_engine import get_diff_engine, persist_deltas

    settings = get_settings()
    if not settings.diff_engine_enabled:
        return

    deltas = await get_diff_engine().observe(
        slug, source=source, implied_yes=float(implied_yes)
    )
    if not deltas:
        return

    # Feed the same deltas to the alignment scorer (T04) — another in-process
    # consumer. Whale/news deltas (T05/T06) feed the scorer from their workers.
    from app.signals.alignment import get_alignment_scorer, persist_alignment

    score = None
    if settings.alignment_enabled:
        score = get_alignment_scorer().observe_deltas(deltas)

    async with AsyncSessionLocal() as db:
        try:
            # Price deltas must reference a locally-mirrored market — drop stale
            # ghost slugs so the per-market activity feed stays clean (E15/E16).
            await persist_deltas(db, deltas, require_market=True)
            if score is not None:
                await persist_alignment(db, score)
            await db.commit()
        except Exception:  # noqa: BLE001 - a delta-persist failure must not drop the caller
            await db.rollback()
            logger.warning(
                "Diff-engine delta persist failed for %s", slug, exc_info=True
            )


async def _run_diff_engine(event: StreamEvent) -> None:
    """Feed a stream event through the diff engine; persist any DeltaEvents (T03)."""
    # Only price ticks feed the diff engine today. The streams' orderbook_delta
    # payloads carry best-quote PRICES (Kalshi: price/delta/side; Polymarket:
    # best bid/ask), not aggregate bid/ask SIZES, so wiring them to bid_size/
    # ask_size would emit bogus orderbook_flip signals. orderbook_flip is fully
    # unit-tested and stays ready for a real size source (future ticket).
    if event.kind is StreamEventKind.TICK and event.payload.get("yes") is not None:
        await run_price_signal_pipeline(
            event.market_slug, event.source, float(event.payload["yes"])
        )


async def _persist_tick_event(event: StreamEvent) -> None:
    from app.observability.metrics import record_stream_event

    record_stream_event(source=event.source, kind=event.kind.value)

    if event.kind is StreamEventKind.TICK and event.payload.get("yes") is not None:
        from app.workers.price_feed_worker import persist_and_publish_tick

        async with AsyncSessionLocal() as db:
            try:
                await persist_and_publish_tick(
                    db,
                    slug=event.market_slug,
                    yes=float(event.payload["yes"]),
                    source=event.source,
                    book=event.source,
                )
                await db.commit()
            except Exception:  # noqa: BLE001 - one bad event must not drop the stream
                await db.rollback()
                logger.warning(
                    "Stream tick persist failed for %s", event.market_slug, exc_info=True
                )

    # Every event (tick and orderbook delta) also feeds the diff engine.
    await _run_diff_engine(event)


async def run_kalshi_stream_loop(
    *,
    ws_url: str,
    reconnect_cap_sec: float,
    heartbeat_timeout_sec: float,
    api_key_id: str = "",
    signing_pem: str = "",
) -> None:
    """Resolve tracked tickers and run the Kalshi stream forever.

    If no Kalshi markets are mirrored yet, sleeps and retries — the ingest loop
    may populate them shortly after startup.
    """
    import asyncio

    while True:
        mapping = await kalshi_ticker_slug_map()
        if not mapping:
            logger.info("Kalshi stream: no open mirrored markets yet, retrying in 60s")
            await asyncio.sleep(60)
            continue
        stream = KalshiMarketStream(
            mapping,
            ws_url=ws_url,
            reconnect_cap_sec=reconnect_cap_sec,
            heartbeat_timeout_sec=heartbeat_timeout_sec,
            api_key_id=api_key_id,
            signing_pem=signing_pem,
        )
        logger.info("Kalshi stream: subscribing to %d markets", len(mapping))
        await stream.run(_persist_tick_event)


async def run_polymarket_stream_loop(
    *,
    ws_url: str,
    reconnect_cap_sec: float,
    heartbeat_timeout_sec: float,
) -> None:
    """Resolve tracked YES token ids and run the Polymarket CLOB stream forever."""
    import asyncio

    while True:
        mapping = await polymarket_token_slug_map()
        if not mapping:
            logger.info(
                "Polymarket stream: no open mirrored markets with token ids yet, "
                "retrying in 60s"
            )
            await asyncio.sleep(60)
            continue
        stream = PolymarketMarketStream(
            mapping,
            ws_url=ws_url,
            reconnect_cap_sec=reconnect_cap_sec,
            heartbeat_timeout_sec=heartbeat_timeout_sec,
        )
        logger.info("Polymarket stream: subscribing to %d markets", len(mapping))
        await stream.run(_persist_tick_event)
