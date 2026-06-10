"""Deterministic candle / snapshot generation matching frontend mock-data.ts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


def _i32(value: int) -> int:
    value &= 0xFFFFFFFF
    if value >= 0x80000000:
        value -= 0x100000000
    return value


def _imul(a: int, b: int) -> int:
    return _i32(a * b)


def hash_seed(value: str) -> int:
    h = 2166136261
    for char in value:
        h ^= ord(char)
        h = _imul(h, 16777619)
    return h & 0xFFFFFFFF


def mulberry32(seed: int):
    a = seed & 0xFFFFFFFF

    def random() -> float:
        nonlocal a
        a = _i32(a)
        a = _i32(a + 0x6D2B79F5)
        # Mask before shifting to match JS unsigned `>>>` (zero-fill, not sign-fill).
        t = _imul(a ^ ((a & 0xFFFFFFFF) >> 15), (1 | a) & 0xFFFFFFFF)
        t = _i32(_imul(t ^ ((t & 0xFFFFFFFF) >> 7), (61 | t) & 0xFFFFFFFF) ^ t)
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    return random


@dataclass(frozen=True)
class SeedCandle:
    time: int
    open: float
    high: float
    low: float
    close: float


_SEED_EPOCH = datetime(2026, 6, 2, 17, 0, 0, tzinfo=UTC)


def generate_candles(
    slug: str,
    points: int,
    end_price: float,
    step_sec: int,
    *,
    now: datetime | None = None,
) -> list[SeedCandle]:
    rand = mulberry32(hash_seed(slug))
    if now is None:
        now = _SEED_EPOCH
    now_ts = int(now.timestamp())

    closes: list[float] = [end_price]
    for _ in range(1, points):
        drift = (rand() - 0.5) * 0.035
        prev = closes[0]
        nxt = prev - drift
        nxt = min(0.94, max(0.06, nxt))
        closes.insert(0, nxt)

    candles: list[SeedCandle] = []
    for i in range(points):
        close = closes[i]
        open_ = close if i == 0 else closes[i - 1]
        wig = 0.012 + rand() * 0.02
        high = min(0.97, max(open_, close) + wig * rand())
        low = max(0.03, min(open_, close) - wig * rand())
        candles.append(
            SeedCandle(
                time=now_ts - (points - 1 - i) * step_sec,
                open=open_,
                high=high,
                low=low,
                close=close,
            )
        )
    return candles


def captured_at_from_unix(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=UTC)


def hour_bucket_start(value: datetime) -> datetime:
    normalized = value.astimezone(UTC)
    return normalized.replace(minute=0, second=0, microsecond=0)


def bucket_snapshots(
    implied_values: list[tuple[datetime, float]],
) -> list[SeedCandle]:
    if not implied_values:
        return []

    buckets: dict[datetime, list[tuple[datetime, float]]] = {}
    for captured_at, implied in implied_values:
        start = hour_bucket_start(captured_at)
        buckets.setdefault(start, []).append((captured_at, implied))

    candles: list[SeedCandle] = []
    for start in sorted(buckets):
        rows = sorted(buckets[start], key=lambda row: row[0])
        prices = [price for _, price in rows]
        candles.append(
            SeedCandle(
                time=int(start.timestamp()),
                open=rows[0][1],
                high=max(prices),
                low=min(prices),
                close=rows[-1][1],
            )
        )
    return candles


def pad_candles(
    candles: list[SeedCandle],
    slug: str,
    points: int,
    end_price: float,
    step_sec: int,
) -> list[SeedCandle]:
    if len(candles) >= points:
        return candles[-points:]

    needed = points - len(candles)
    if candles:
        anchor = datetime.fromtimestamp(candles[0].time, tz=UTC) - timedelta(
            seconds=step_sec
        )
        pad_end = candles[0].open
    else:
        anchor = datetime.now(UTC)
        pad_end = end_price

    pad = generate_candles(slug, needed, pad_end, step_sec, now=anchor)
    combined = pad + candles
    return combined[-points:]
