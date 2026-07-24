from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.indicators import router as indicators_router
from app.db.session import get_db
from app.services.technical_analysis_service import calculate_indicators, classify_regime
from app.services.market_service import MarketService


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


@pytest.mark.parametrize(
    ("indicators", "expected"),
    [
        ({"sma_20": 0.7, "sma_50": 0.5, "adx_14": 21.0}, "trending_up"),
        ({"sma_20": 0.4, "sma_50": 0.6, "adx_14": 21.0}, "trending_down"),
        ({"sma_20": 0.7, "sma_50": 0.5, "adx_14": 20.0}, "range"),
        ({"sma_20": None, "sma_50": None, "adx_14": None}, "insufficient_data"),
    ],
)
def test_regime_classifier_is_deterministic(indicators: dict[str, object], expected: str) -> None:
    assert classify_regime(indicators) == expected


async def _indicators_client(db_session) -> AsyncClient:
    app = FastAPI()
    app.include_router(indicators_router)

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_indicators_endpoint_returns_the_frozen_public_contract(db_session) -> None:
    await MarketService(db_session).seed_catalog_markets()

    async with await _indicators_client(db_session) as client:
        response = await client.get("/api/v1/markets/nba-2025-01-15-lal-bos/indicators?window=90")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"slug", "points", "indicators", "regime", "paper_trading_only"}
    assert body["slug"] == "nba-2025-01-15-lal-bos"
    assert body["paper_trading_only"] is True
    assert len(body["points"]) == 90
    assert set(body["points"][0]) == {"t", "close"}
    assert set(body["indicators"]) == {
        "rsi_14",
        "macd",
        "sma_20",
        "sma_50",
        "ema_12",
        "bollinger",
        "adx_14",
    }
    assert body["regime"] in {"trending_up", "trending_down", "range", "insufficient_data"}


@pytest.mark.asyncio
@pytest.mark.parametrize("window", [19, 366])
async def test_indicators_endpoint_rejects_out_of_contract_windows(db_session, window: int) -> None:
    async with await _indicators_client(db_session) as client:
        response = await client.get(f"/api/v1/markets/nba-2025-01-15-lal-bos/indicators?window={window}")

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_indicators_endpoint_returns_404_for_unknown_market(db_session) -> None:
    async with await _indicators_client(db_session) as client:
        response = await client.get("/api/v1/markets/unknown-market/indicators")

    assert response.status_code == 404
