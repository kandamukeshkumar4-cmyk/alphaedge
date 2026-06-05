from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OddsSnapshot, SignalEvent
from app.signals.arbitrage import BinaryMarketQuote, find_binary_arbitrage
from app.signals.dutching import DutchingOutcome, evaluate_dutching
from app.signals.matching import ResolutionMatch, ResolutionTerms, match_resolution_terms


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
