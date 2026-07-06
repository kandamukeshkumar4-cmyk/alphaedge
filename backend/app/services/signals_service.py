from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Market, OddsSnapshot, SignalEvent
from app.forecasting.predictor import predict_market
from app.signals.arbitrage import BinaryMarketQuote, find_binary_arbitrage
from app.signals.dutching import DutchingOutcome, evaluate_dutching
from app.signals.matching import ResolutionMatch, ResolutionTerms, match_resolution_terms
from app.signals.screeners import (
    ScreenerHit,
    screen_expiry_fade,
    screen_momentum,
)


SIGNAL_DISCLAIMER = "Research signal only. No execution. Simulated funds only."
_ALLOWED_PLATFORM_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-")


class InvalidSignalRequest(ValueError):
    pass


class SignalsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def arbitrage_signal(self, platform: str, market_id: str) -> dict[str, Any]:
        platform = _normalize_platform(platform)
        target = await self._latest_snapshot(platform, market_id)
        if target is None:
            raise ValueError("Market snapshot not found")

        candidates = await self._candidate_binary_snapshots(target)
        if not candidates:
            raise ValueError("No comparison market snapshots found")

        candidate, resolution_match = _best_binary_candidate(target, candidates)
        signal = find_binary_arbitrage(
            yes_market=BinaryMarketQuote(
                platform=_platform_from_source(target.source),
                market_id=target.platform_market_id or target.market_slug,
                yes_price=_snapshot_price(target),
                no_price=Decimal("1.0000") - _snapshot_price(target),
            ),
            no_market=BinaryMarketQuote(
                platform=_platform_from_source(candidate.source),
                market_id=candidate.platform_market_id or candidate.market_slug,
                yes_price=_snapshot_price(candidate),
                no_price=Decimal("1.0000") - _snapshot_price(candidate),
            ),
            resolution_match=resolution_match,
        )
        payload = {
            "paper_trading_only": True,
            "disclaimer": SIGNAL_DISCLAIMER,
            "signal": {
                **_jsonable(asdict(signal)),
                "match_reasons": list(resolution_match.reasons),
            },
        }
        if signal.headline_eligible:
            await self._persist_signal("arbitrage", platform, market_id, True, payload)
        return payload

    async def dutching_signal(self, platform: str, market_id: str) -> dict[str, Any]:
        platform = _normalize_platform(platform)
        snapshots = await self._latest_market_snapshots(platform, market_id)
        if not snapshots:
            raise ValueError("Market snapshots not found")

        exhaustive = all(bool(row.snapshot_metadata.get("exhaustive")) for row in snapshots)
        mutually_exclusive = all(
            bool(row.snapshot_metadata.get("mutually_exclusive")) for row in snapshots
        )
        result = evaluate_dutching(
            [
                DutchingOutcome(
                    name=row.outcome_name,
                    price=_snapshot_price(row),
                )
                for row in snapshots
            ],
            exhaustive=exhaustive,
            mutually_exclusive=mutually_exclusive,
        )
        payload = {
            "paper_trading_only": True,
            "disclaimer": SIGNAL_DISCLAIMER,
            "signal": _jsonable(asdict(result)),
        }
        if result.risk_free:
            await self._persist_signal("dutching", platform, market_id, True, payload)
        return payload

    async def forecast_signal(self, platform: str, market_id: str) -> dict[str, Any]:
        platform = _normalize_platform(platform)
        target = await self._latest_snapshot(platform, market_id)
        if target is None:
            raise ValueError("Market snapshot not found")

        implied = float(_snapshot_price(target))
        features = {
            "market_slug": target.market_slug or market_id,
            "implied_yes": implied,
            "market_implied": implied,
        }
        metadata = target.snapshot_metadata or {}
        if metadata.get("forecast_comparisons"):
            features["forecast_comparisons"] = metadata["forecast_comparisons"]
        if metadata.get("forecast_trades"):
            features["forecast_trades"] = metadata["forecast_trades"]

        prediction = predict_market(features)
        clv_mean = prediction.clv.mean_clv if prediction.clv is not None else None
        payload = {
            "paper_trading_only": True,
            "disclaimer": SIGNAL_DISCLAIMER,
            "platform": platform,
            "market_id": market_id,
            "signal": {
                "model_prob": prediction.predicted_prob,
                "confidence": prediction.confidence,
                "edge": prediction.edge,
                "is_edge": prediction.is_edge,
                "reason": prediction.reason,
                "clv": clv_mean,
                "clv_positive": prediction.clv.clv_positive if prediction.clv else False,
                "trade_count": prediction.clv.trade_count if prediction.clv else 0,
                "outcome": prediction.outcome,
                "executable_price": prediction.executable_price,
            },
        }
        if prediction.is_edge:
            await self._persist_signal("forecast", platform, market_id, True, payload)
        return payload

    async def screeners(
        self,
        *,
        screen: str = "all",
        lookback_hours: float = 168.0,
        series_points: int = 6,
        limit: int = 50,
        persist: bool = True,
        headline_min_strength: float = 0.5,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Run the deterministic expiry-fade + momentum screens over recent odds
        snapshots and persist strong hits as ``screener:*`` SignalEvents.

        Signals only — the result never sizes or places a trade."""
        screen = screen.strip().lower()
        if screen not in {"all", "expiry_fade", "momentum"}:
            raise InvalidSignalRequest("Invalid screen")
        now = now or datetime.now(timezone.utc)

        result = await self.session.execute(
            select(OddsSnapshot)
            .where(OddsSnapshot.market_slug.isnot(None))
            .order_by(OddsSnapshot.market_slug, OddsSnapshot.captured_at)
        )
        snapshots = list(result.scalars().all())

        series_by_slug: dict[str, list[float]] = {}
        latest_by_slug: dict[str, OddsSnapshot] = {}
        for row in snapshots:
            slug = row.market_slug
            series_by_slug.setdefault(slug, []).append(float(_snapshot_price(row)))
            latest_by_slug[slug] = row  # rows ascending → last wins

        lock_at_by_slug: dict[str, datetime | None] = {}
        if latest_by_slug:
            markets = await self.session.execute(
                select(Market.slug, Market.lock_at).where(
                    Market.slug.in_(list(latest_by_slug.keys()))
                )
            )
            lock_at_by_slug = {slug: lock_at for slug, lock_at in markets.all()}

        hits: list[ScreenerHit] = []
        for slug, latest in latest_by_slug.items():
            series = series_by_slug[slug][-series_points:]
            if screen in {"all", "momentum"}:
                hit = screen_momentum(slug, series)
                if hit is not None:
                    hits.append(hit)
            if screen in {"all", "expiry_fade"}:
                lock_at = lock_at_by_slug.get(slug)
                hours = _hours_between(now, lock_at)
                hit = screen_expiry_fade(slug, float(_snapshot_price(latest)), hours)
                if hit is not None:
                    hits.append(hit)

        hits.sort(key=lambda h: h.strength, reverse=True)
        hits = hits[:limit]

        if persist:
            for hit in hits:
                platform = _platform_from_source(latest_by_slug[hit.market_slug].source)
                await self._persist_signal(
                    f"screener:{hit.kind}"[:32],
                    platform,
                    hit.market_slug,
                    hit.strength >= headline_min_strength,
                    {
                        "paper_trading_only": True,
                        "disclaimer": SIGNAL_DISCLAIMER,
                        "signal": {
                            "kind": hit.kind,
                            "direction": hit.direction,
                            "strength": hit.strength,
                            "reason": hit.reason,
                            **hit.detail,
                        },
                    },
                )

        return {
            "paper_trading_only": True,
            "disclaimer": SIGNAL_DISCLAIMER,
            "screen": screen,
            "count": len(hits),
            "hits": [
                {
                    "kind": hit.kind,
                    "market_slug": hit.market_slug,
                    "direction": hit.direction,
                    "strength": hit.strength,
                    "reason": hit.reason,
                    "detail": hit.detail,
                }
                for hit in hits
            ],
        }

    async def _latest_snapshot(self, platform: str, market_id: str) -> OddsSnapshot | None:
        result = await self.session.execute(
            select(OddsSnapshot)
            .where(
                OddsSnapshot.platform_market_id == market_id,
                OddsSnapshot.source.like(f"{platform}%"),
            )
            .order_by(OddsSnapshot.captured_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _latest_market_snapshots(self, platform: str, market_id: str) -> list[OddsSnapshot]:
        result = await self.session.execute(
            select(OddsSnapshot)
            .where(
                OddsSnapshot.platform_market_id == market_id,
                OddsSnapshot.source.like(f"{platform}%"),
            )
            .order_by(OddsSnapshot.captured_at.desc())
        )
        rows = list(result.scalars().all())
        latest_by_outcome: dict[str, OddsSnapshot] = {}
        for row in rows:
            if row.outcome_name not in latest_by_outcome:
                latest_by_outcome[row.outcome_name] = row
        return list(latest_by_outcome.values())

    async def _candidate_binary_snapshots(self, target: OddsSnapshot) -> list[OddsSnapshot]:
        result = await self.session.execute(
            select(OddsSnapshot)
            .where(
                OddsSnapshot.platform_market_id != target.platform_market_id,
                OddsSnapshot.market_type == "binary",
            )
            .order_by(OddsSnapshot.captured_at.desc())
        )
        rows = [
            row
            for row in result.scalars().all()
            if _platform_from_source(row.source) != _platform_from_source(target.source)
        ]
        latest_by_market: dict[str, OddsSnapshot] = {}
        for row in rows:
            market_id = row.platform_market_id or row.market_slug
            if market_id not in latest_by_market:
                latest_by_market[market_id] = row
        return list(latest_by_market.values())

    async def _persist_signal(
        self,
        signal_type: str,
        platform: str,
        market_id: str,
        headline_eligible: bool,
        payload: dict[str, Any],
    ) -> None:
        self.session.add(
            SignalEvent(
                signal_type=signal_type,
                platform=platform,
                market_id=market_id,
                headline_eligible=headline_eligible,
                payload=payload,
            )
        )
        await self.session.flush()


def _resolution_terms(snapshot: OddsSnapshot) -> ResolutionTerms:
    metadata = snapshot.snapshot_metadata or {}
    return ResolutionTerms(
        platform=_platform_from_source(snapshot.source),
        market_id=snapshot.platform_market_id or snapshot.market_slug,
        title=snapshot.title or "",
        event_id=snapshot.event_id,
        normalized_entities=tuple(metadata.get("normalized_entities") or ()),
        close_at=snapshot.close_at,
        resolution_source=metadata.get("resolution_source"),
        resolution_rules=str(metadata.get("resolution_rules") or ""),
    )


def _best_binary_candidate(
    target: OddsSnapshot,
    candidates: list[OddsSnapshot],
) -> tuple[OddsSnapshot, ResolutionMatch]:
    target_terms = _resolution_terms(target)
    scored = [
        (candidate, match_resolution_terms(target_terms, _resolution_terms(candidate)))
        for candidate in candidates
    ]
    scored.sort(
        key=lambda item: (
            item[1].confirmed,
            item[1].confidence,
            item[0].captured_at,
        ),
        reverse=True,
    )
    return scored[0]


def _hours_between(now: datetime, close_at: datetime | None) -> float | None:
    if close_at is None:
        return None
    if close_at.tzinfo is None:
        close_at = close_at.replace(tzinfo=timezone.utc)
    return (close_at - now).total_seconds() / 3600.0


def _platform_from_source(source: str) -> str:
    return source.split(".", 1)[0].split(":", 1)[0]


def _normalize_platform(platform: str) -> str:
    normalized = platform.strip().lower()
    if not normalized or any(char not in _ALLOWED_PLATFORM_CHARS for char in normalized):
        raise InvalidSignalRequest("Invalid platform")
    return normalized


def _snapshot_price(snapshot: OddsSnapshot) -> Decimal:
    return Decimal(str(snapshot.price if snapshot.price is not None else snapshot.implied_yes))


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value
