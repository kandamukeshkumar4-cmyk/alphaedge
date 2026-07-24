from __future__ import annotations

import pytest

from app.services.technical_analysis_service import calculate_indicators


def test_flat_series_has_known_neutral_values() -> None:
    indicators = calculate_indicators([0.5] * 40)

    assert indicators["rsi_14"] == 50.0
    assert indicators["macd"] == {"macd": 0.0, "signal": 0.0, "hist": 0.0}
    assert indicators["sma_20"] == 0.5
    assert indicators["sma_50"] is None
    assert indicators["ema_12"] == 0.5
    assert indicators["bollinger"] == {"upper": 0.5, "mid": 0.5, "lower": 0.5}
    assert indicators["adx_14"] == 0.0


def test_rising_series_matches_hand_calculated_latest_values() -> None:
    closes = [0.2 + index * 0.01 for index in range(60)]

    indicators = calculate_indicators(closes)

    assert indicators["rsi_14"] == 100.0
    assert indicators["sma_20"] == pytest.approx(0.695)
    assert indicators["sma_50"] == pytest.approx(0.545)
    assert indicators["ema_12"] == pytest.approx(0.735)
    assert indicators["macd"] == {
        "macd": pytest.approx(0.07),
        "signal": pytest.approx(0.07),
        "hist": pytest.approx(0.0, abs=1e-12),
    }
    assert indicators["adx_14"] == 100.0


def test_each_indicator_reports_none_when_its_period_is_unavailable() -> None:
    indicators = calculate_indicators([0.5] * 14)

    assert indicators["rsi_14"] is None
    assert indicators["macd"] == {"macd": None, "signal": None, "hist": None}
    assert indicators["sma_20"] is None
    assert indicators["sma_50"] is None
    assert indicators["ema_12"] == 0.5
    assert indicators["bollinger"] == {"upper": None, "mid": None, "lower": None}
    assert indicators["adx_14"] is None
