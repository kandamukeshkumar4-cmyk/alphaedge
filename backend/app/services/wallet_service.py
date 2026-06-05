from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.connectors.onchain import OnchainWalletPosition
from app.db.models import TrackedWallet, WalletPosition
from app.services.signals_service import InvalidSignalRequest
from app.signals.smart_money import WalletPerformance, is_qualified_wallet


SMART_MONEY_DISCLAIMER = "Research signal only. No execution. Simulated funds only."
_ALLOWED_PLATFORM_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-")


class WalletService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_wallet_positions(
        self,
        platform: str,
        positions: list[OnchainWalletPosition],
    ) -> int:
        platform = _normalize_platform(platform)
        inserted = 0
        for position in positions:
            wallet = await self._get_or_create_wallet(position.wallet_address)
            wallet.realized_pnl = position.realized_pnl
            wallet.unrealized_pnl = position.unrealized_pnl
            wallet.roi = position.roi
            wallet.hit_rate = position.hit_rate
            wallet.total_trades = position.total_trades
            wallet.qualified = is_qualified_wallet(
                WalletPerformance(
                    roi=position.roi,
                    realized_pnl=position.realized_pnl,
                    total_trades=position.total_trades,
                )
            )
            self.session.add(
                WalletPosition(
                    tracked_wallet_id=wallet.id,
                    platform=platform,
                    market_id=position.market_id,
                    outcome=position.outcome,
                    side=position.side,
                    quantity=position.quantity,
                    average_price=position.average_price,
                    current_price=position.current_price,
                    realized_pnl=position.realized_pnl,
                    unrealized_pnl=position.unrealized_pnl,
                    total_pnl=position.total_pnl,
                )
            )
            inserted += 1
        await self.session.flush()
        return inserted

    async def smart_money_signal(self, platform: str, market_id: str) -> dict[str, Any]:
        platform = _normalize_platform(platform)
        result = await self.session.execute(
            select(WalletPosition, TrackedWallet)
            .join(TrackedWallet, WalletPosition.tracked_wallet_id == TrackedWallet.id)
            .where(
                WalletPosition.platform == platform,
                WalletPosition.market_id == market_id,
                TrackedWallet.qualified.is_(True),
                WalletPosition.quantity > 0,
            )
            .order_by(WalletPosition.captured_at.desc(), WalletPosition.total_pnl.desc())
        )
        latest_by_wallet_outcome: dict[tuple[str, str], tuple[WalletPosition, TrackedWallet]] = {}
        for position, wallet in result.all():
            key = (wallet.wallet_address, position.outcome)
            if key not in latest_by_wallet_outcome:
                latest_by_wallet_outcome[key] = (position, wallet)

        positions = [
            _position_payload(position, wallet)
            for position, wallet in latest_by_wallet_outcome.values()
        ]
        return {
            "paper_trading_only": True,
            "read_only": True,
            "disclaimer": SMART_MONEY_DISCLAIMER,
            "platform": platform,
            "market_id": market_id,
            "tracked_wallet_count": len(positions),
            "positions": positions,
        }

    async def _get_or_create_wallet(self, wallet_address: str) -> TrackedWallet:
        normalized = wallet_address.lower()
        result = await self.session.execute(
            select(TrackedWallet).where(TrackedWallet.wallet_address == normalized)
        )
        wallet = result.scalar_one_or_none()
        if wallet is not None:
            return wallet
        wallet = TrackedWallet(wallet_address=normalized)
        self.session.add(wallet)
        await self.session.flush()
        return wallet


def _position_payload(position: WalletPosition, wallet: TrackedWallet) -> dict[str, Any]:
    return {
        "wallet_address": wallet.wallet_address,
        "label": wallet.label,
        "side": position.side,
        "outcome": position.outcome,
        "quantity": _json_number(position.quantity),
        "average_price": _json_number(position.average_price),
        "current_price": _json_number(position.current_price),
        "realized_pnl": _json_number(position.realized_pnl),
        "unrealized_pnl": _json_number(position.unrealized_pnl),
        "total_pnl": _json_number(position.total_pnl),
        "roi": _json_number(wallet.roi),
        "hit_rate": _json_number(wallet.hit_rate),
        "total_trades": wallet.total_trades,
    }


def _normalize_platform(platform: str) -> str:
    normalized = platform.strip().lower()
    if not normalized or any(char not in _ALLOWED_PLATFORM_CHARS for char in normalized):
        raise InvalidSignalRequest("Invalid platform")
    return normalized


def _json_number(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)
