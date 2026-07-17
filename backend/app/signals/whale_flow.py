"""Whale flow signal (Loop V58 D1).

Polls Polymarket public data-api for large trades on tracked markets, persists
whale_events, and derives per-market whale_pressure in [-1, 1].

Technique sources (READ ONLY, adapted — not vendored):
- polymarket-whales: large-trade threshold + poll cadence for whale alerts
- polyterm DataAPIClient: global trade tape with filterType=CASH/filterAmount
- polymarket-whale-watcher: wallet-level notional sizing for "whale" classification

Analysis only — never places orders. Every observation is timestamped at
capture so consumers can enforce pre-close leakage filters.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

# Default cash notional (USD) above which a trade is a "whale" observation.
DEFAULT_MIN_NOTIONAL = Decimal("1000")
DEFAULT_PRESSURE_WINDOW_SEC = 3600.0
DEFAULT_MIN_POLL_INTERVAL_SEC = 60.0

# Circuit breaker (process-local; mirrors nemotron_signal pattern).
_FAILURE_THRESHOLD = 3
_COOLDOWN_SEC = 300.0
_consecutive_failures = 0
_circuit_open_until: float | None = None
_last_poll_at: float = 0.0


@dataclass(frozen=True)
class LargeTrade:
    """Normalized large-trade row from the public data-api tape."""

    wallet: str
    side: str  # BUY / SELL
    outcome: str  # YES / NO
    size: Decimal
    price: Decimal
    notional: Decimal
    market_slug: str
    market_id: str
    tx_hash: str | None
    trade_at: datetime | None


@dataclass(frozen=True)
class WhalePressure:
    """Per-market whale pressure feature in [-1, 1]."""

    market_slug: str
    pressure: float  # -1 (heavy NO / sell-YES) .. +1 (heavy YES / buy-YES)
    event_count: int
    net_notional: float
    total_notional: float
    window_sec: float
    as_of: datetime  # capture-time clock; never post-close resolution


# Process-local pressure cache for the sync prediction graph node (D4).
_PRESSURE_CACHE: dict[str, WhalePressure] = {}


def cache_whale_pressure(pressure: WhalePressure) -> None:
    _PRESSURE_CACHE[pressure.market_slug] = pressure


def get_cached_whale_pressure(market_slug: str) -> WhalePressure | None:
    return _PRESSURE_CACHE.get(market_slug)


def reset_whale_flow_state() -> None:
    """Test helper — clear circuit breaker, rate-limit clock, and pressure cache."""
    global _consecutive_failures, _circuit_open_until, _last_poll_at
    _consecutive_failures = 0
    _circuit_open_until = None
    _last_poll_at = 0.0
    _PRESSURE_CACHE.clear()


def circuit_is_open(*, now: float | None = None) -> bool:
    ts = time.monotonic() if now is None else now
    return _circuit_open_until is not None and ts < _circuit_open_until


def record_poll_success() -> None:
    global _consecutive_failures, _circuit_open_until, _last_poll_at
    _consecutive_failures = 0
    _circuit_open_until = None
    _last_poll_at = time.monotonic()


def record_poll_failure() -> None:
    global _consecutive_failures, _circuit_open_until, _last_poll_at
    _consecutive_failures += 1
    _last_poll_at = time.monotonic()
    if _consecutive_failures >= _FAILURE_THRESHOLD:
        _circuit_open_until = time.monotonic() + _COOLDOWN_SEC


def rate_limit_ok(
    *,
    min_interval_sec: float = DEFAULT_MIN_POLL_INTERVAL_SEC,
    now: float | None = None,
) -> bool:
    """Polite poll gate: True when enough wall time has elapsed since last poll."""
    ts = time.monotonic() if now is None else now
    if _last_poll_at <= 0:
        return True
    return (ts - _last_poll_at) >= min_interval_sec


def _dec(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _wallet_of(row: dict[str, Any]) -> str:
    return str(
        row.get("proxyWallet")
        or row.get("wallet")
        or row.get("user")
        or row.get("maker_address")
        or row.get("maker")
        or row.get("taker_address")
        or row.get("taker")
        or row.get("address")
        or ""
    ).lower()


def _outcome_of(row: dict[str, Any]) -> str:
    raw = str(row.get("outcome") or row.get("tokenOutcome") or "").strip().upper()
    if raw in {"YES", "NO"}:
        return raw
    idx = row.get("outcomeIndex")
    if idx is not None:
        try:
            return "YES" if int(idx) == 0 else "NO"
        except (TypeError, ValueError):
            pass
    return "YES"


def _side_of(row: dict[str, Any]) -> str:
    raw = str(row.get("side") or "").strip().upper()
    if raw in {"BUY", "SELL"}:
        return raw
    # Some payloads use "bid"/"ask"
    if raw in {"BID", "B"}:
        return "BUY"
    if raw in {"ASK", "A"}:
        return "SELL"
    return "BUY"


def _parse_trade_at(row: dict[str, Any]) -> datetime | None:
    ts = row.get("timestamp") or row.get("createdAt") or row.get("matchTime")
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        # data-api uses unix seconds; some feeds use ms
        if ts > 1e12:
            ts = ts / 1000.0
        try:
            return datetime.fromtimestamp(float(ts), tz=UTC)
        except (OSError, OverflowError, ValueError):
            return None
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def normalize_large_trades(
    payload: Any,
    *,
    min_notional: Decimal = DEFAULT_MIN_NOTIONAL,
    market_slugs: set[str] | None = None,
) -> list[LargeTrade]:
    """Normalize data-api /trades payload into LargeTrade rows above threshold.

    Pure / network-free. Optional ``market_slugs`` filters to tracked markets
    only (slug or market_id match).
    """
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    tracked = {s.lower() for s in market_slugs} if market_slugs else None
    out: list[LargeTrade] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        price = _dec(row.get("price"))
        size = _dec(row.get("size") or row.get("shares") or row.get("amount"))
        notional = _dec(row.get("notional") or row.get("usdcSize") or row.get("cash"))
        if notional <= 0 and price > 0 and size > 0:
            notional = (price * size).quantize(Decimal("0.0001"))
        if notional < min_notional:
            continue
        market_id = str(
            row.get("conditionId") or row.get("market") or row.get("marketId") or ""
        )
        slug = str(row.get("slug") or row.get("marketSlug") or market_id or "")
        if not slug:
            continue
        if tracked is not None:
            key = slug.lower()
            mid = market_id.lower()
            if key not in tracked and mid not in tracked:
                continue
        wallet = _wallet_of(row) or "unknown"
        tx = row.get("transactionHash") or row.get("tx_hash") or row.get("txHash")
        out.append(
            LargeTrade(
                wallet=wallet,
                side=_side_of(row),
                outcome=_outcome_of(row),
                size=size,
                price=price,
                notional=notional,
                market_slug=slug,
                market_id=market_id,
                tx_hash=str(tx) if tx else None,
                trade_at=_parse_trade_at(row),
            )
        )
    return out


def signed_notional(trade: LargeTrade) -> Decimal:
    """YES-direction signed cash flow: +buy YES / -sell YES; flip for NO.

    Convention: positive pressure favors YES resolution.
    """
    sign = Decimal("1") if trade.side == "BUY" else Decimal("-1")
    if trade.outcome == "NO":
        sign = -sign
    return sign * trade.notional


def compute_whale_pressure(
    events: Iterable[LargeTrade | dict[str, Any]],
    *,
    market_slug: str,
    window_sec: float = DEFAULT_PRESSURE_WINDOW_SEC,
    as_of: datetime | None = None,
) -> WhalePressure:
    """Derive whale_pressure ∈ [-1, 1] from recent large trades.

    Uses tanh(net / scale) so a few huge trades saturate near ±1 without
    exploding, while balanced two-sided flow centers near 0.
    """
    now = as_of or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    cutoff = now.timestamp() - window_sec
    net = Decimal("0")
    total = Decimal("0")
    count = 0
    for raw in events:
        if isinstance(raw, LargeTrade):
            trade = raw
        else:
            trade = LargeTrade(
                wallet=str(raw.get("wallet") or "unknown"),
                side=str(raw.get("side") or "BUY").upper(),
                outcome=str(raw.get("outcome") or "YES").upper(),
                size=_dec(raw.get("size")),
                price=_dec(raw.get("price")),
                notional=_dec(raw.get("notional")),
                market_slug=str(raw.get("market_slug") or market_slug),
                market_id=str(raw.get("market_id") or ""),
                tx_hash=raw.get("tx_hash"),
                trade_at=raw.get("trade_at") or raw.get("captured_at"),
            )
        if trade.market_slug != market_slug and trade.market_id != market_slug:
            continue
        ts = trade.trade_at
        if ts is not None:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            if ts.timestamp() < cutoff:
                continue
        sn = signed_notional(trade)
        net += sn
        total += abs(trade.notional)
        count += 1
    if total <= 0 or count == 0:
        return WhalePressure(
            market_slug=market_slug,
            pressure=0.0,
            event_count=0,
            net_notional=0.0,
            total_notional=0.0,
            window_sec=window_sec,
            as_of=now,
        )
    # Scale ~ median large trade so pressure is meaningful around ~$5k net.
    scale = float(max(total / Decimal(str(count)), Decimal("1000")))
    pressure = math.tanh(float(net) / scale)
    pressure = max(-1.0, min(1.0, pressure))
    return WhalePressure(
        market_slug=market_slug,
        pressure=round(pressure, 6),
        event_count=count,
        net_notional=float(net),
        total_notional=float(total),
        window_sec=window_sec,
        as_of=now,
    )


def trade_dedupe_key(trade: LargeTrade) -> str:
    """Stable key for idempotent inserts (tx when present, else composite)."""
    if trade.tx_hash:
        return f"tx:{trade.tx_hash}:{trade.side}:{trade.outcome}"
    ta = trade.trade_at.isoformat() if trade.trade_at else ""
    return (
        f"c:{trade.wallet}:{trade.market_slug}:{trade.side}:"
        f"{trade.outcome}:{trade.size}:{trade.price}:{ta}"
    )
