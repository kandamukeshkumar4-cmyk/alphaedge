"""Deterministic technical indicators for prediction-market price series.

This module is read-only analysis.  It has no order-path imports and does not
persist any data.
"""

from __future__ import annotations

from math import isfinite, sqrt
from typing import Sequence

ADX_PERIOD = 14
BOLLINGER_PERIOD = 20
EMA_PERIOD = 12
MACD_FAST_PERIOD = 12
MACD_SIGNAL_PERIOD = 9
MACD_SLOW_PERIOD = 26
RSI_PERIOD = 14
SMA_SHORT_PERIOD = 20
SMA_LONG_PERIOD = 50


def calculate_indicators(
    closes: Sequence[float],
    highs: Sequence[float] | None = None,
    lows: Sequence[float] | None = None,
) -> dict[str, object]:
    """Calculate the latest standard indicator values for an ordered series.

    Missing OHLC extremes are deliberately derived from close.  This keeps the
    calculation available for the existing outcome-price snapshot store, whose
    canonical value is the YES close, while still accepting true candle highs
    and lows when present.
    """
    values = _finite_floats(closes)
    if values is None:
        return _empty_indicators()

    high_values = _finite_floats(highs) if highs is not None else list(values)
    low_values = _finite_floats(lows) if lows is not None else list(values)
    if (
        high_values is None
        or low_values is None
        or len(high_values) != len(values)
        or len(low_values) != len(values)
    ):
        return _empty_indicators()

    macd = _macd(values)
    bollinger = _bollinger(values)
    return {
        "rsi_14": _rsi(values),
        "macd": macd,
        "sma_20": _sma(values, SMA_SHORT_PERIOD),
        "sma_50": _sma(values, SMA_LONG_PERIOD),
        "ema_12": _last_ema(values, EMA_PERIOD),
        "bollinger": bollinger,
        "adx_14": _adx(values, high_values, low_values),
    }


def _empty_indicators() -> dict[str, object]:
    return {
        "rsi_14": None,
        "macd": {"macd": None, "signal": None, "hist": None},
        "sma_20": None,
        "sma_50": None,
        "ema_12": None,
        "bollinger": {"upper": None, "mid": None, "lower": None},
        "adx_14": None,
    }


def _finite_floats(values: Sequence[float] | None) -> list[float] | None:
    if values is None:
        return None
    try:
        result = [float(value) for value in values]
    except (TypeError, ValueError):
        return None
    return result if all(isfinite(value) for value in result) else None


def _sma(values: Sequence[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _ema_series(values: Sequence[float], period: int) -> list[float]:
    if len(values) < period:
        return []
    current = sum(values[:period]) / period
    result = [current]
    alpha = 2.0 / (period + 1.0)
    for value in values[period:]:
        current += alpha * (value - current)
        result.append(current)
    return result


def _last_ema(values: Sequence[float], period: int) -> float | None:
    series = _ema_series(values, period)
    return series[-1] if series else None


def _rsi(values: Sequence[float], period: int = RSI_PERIOD) -> float | None:
    if len(values) < period + 1:
        return None
    changes = [current - previous for previous, current in zip(values, values[1:])]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        average_gain = (average_gain * (period - 1) + gain) / period
        average_loss = (average_loss * (period - 1) + loss) / period
    if average_loss == 0.0:
        return 100.0 if average_gain > 0.0 else 50.0
    if average_gain == 0.0:
        return 0.0
    relative_strength = average_gain / average_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))


def _macd(values: Sequence[float]) -> dict[str, float | None]:
    if len(values) < MACD_SLOW_PERIOD + MACD_SIGNAL_PERIOD - 1:
        return {"macd": None, "signal": None, "hist": None}
    fast = _ema_series(values, MACD_FAST_PERIOD)
    slow = _ema_series(values, MACD_SLOW_PERIOD)
    fast_offset = MACD_SLOW_PERIOD - MACD_FAST_PERIOD
    line = [fast[index + fast_offset] - slow[index] for index in range(len(slow))]
    signal = _ema_series(line, MACD_SIGNAL_PERIOD)[-1]
    macd = line[-1]
    return {"macd": macd, "signal": signal, "hist": macd - signal}


def _bollinger(values: Sequence[float]) -> dict[str, float | None]:
    if len(values) < BOLLINGER_PERIOD:
        return {"upper": None, "mid": None, "lower": None}
    window = values[-BOLLINGER_PERIOD:]
    mid = sum(window) / BOLLINGER_PERIOD
    deviation = sqrt(sum((value - mid) ** 2 for value in window) / BOLLINGER_PERIOD)
    return {"upper": mid + 2.0 * deviation, "mid": mid, "lower": mid - 2.0 * deviation}


def _adx(
    closes: Sequence[float], highs: Sequence[float], lows: Sequence[float], period: int = ADX_PERIOD
) -> float | None:
    if len(closes) < period * 2:
        return None

    true_ranges: list[float] = []
    plus_moves: list[float] = []
    minus_moves: list[float] = []
    for index in range(1, len(closes)):
        true_ranges.append(
            max(
                highs[index] - lows[index],
                abs(highs[index] - closes[index - 1]),
                abs(lows[index] - closes[index - 1]),
            )
        )
        up_move = highs[index] - highs[index - 1]
        down_move = lows[index - 1] - lows[index]
        plus_moves.append(up_move if up_move > down_move and up_move > 0.0 else 0.0)
        minus_moves.append(down_move if down_move > up_move and down_move > 0.0 else 0.0)

    smoothed_tr = sum(true_ranges[:period])
    smoothed_plus = sum(plus_moves[:period])
    smoothed_minus = sum(minus_moves[:period])
    dx_values = [_directional_index(smoothed_tr, smoothed_plus, smoothed_minus)]
    for index in range(period, len(true_ranges)):
        smoothed_tr = smoothed_tr - (smoothed_tr / period) + true_ranges[index]
        smoothed_plus = smoothed_plus - (smoothed_plus / period) + plus_moves[index]
        smoothed_minus = smoothed_minus - (smoothed_minus / period) + minus_moves[index]
        dx_values.append(_directional_index(smoothed_tr, smoothed_plus, smoothed_minus))

    adx = sum(dx_values[:period]) / period
    for dx in dx_values[period:]:
        adx = (adx * (period - 1) + dx) / period
    return adx


def _directional_index(smoothed_tr: float, smoothed_plus: float, smoothed_minus: float) -> float:
    if smoothed_tr == 0.0:
        return 0.0
    plus_di = 100.0 * smoothed_plus / smoothed_tr
    minus_di = 100.0 * smoothed_minus / smoothed_tr
    denominator = plus_di + minus_di
    return 0.0 if denominator == 0.0 else 100.0 * abs(plus_di - minus_di) / denominator
