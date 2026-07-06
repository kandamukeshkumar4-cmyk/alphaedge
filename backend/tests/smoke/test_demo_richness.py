"""Populated-demo richness assertions (DEMO_RICHNESS=1).

These verify the seeded stack shows populated, non-empty data on every core
screen. Run against a seeded local stack (or the deployed URL):

    DEMO_RICHNESS=1 uv run --extra dev pytest tests/smoke/ -q --base-url http://127.0.0.1:8000

Skipped unless DEMO_RICHNESS=1 so the regular smoke suite stays fast.
"""

import os
from collections.abc import Iterator

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("DEMO_RICHNESS") != "1",
    reason="DEMO_RICHNESS=1 required for richness assertions",
)

MIN_MARKETS = 20
MIN_SNAPSHOTS_PER_MARKET = 30
CANONICAL_SLUG = "nba-2025-01-15-lal-bos"


@pytest.fixture(scope="module")
def client(base_url: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=base_url, timeout=60.0) as c:
        yield c


def test_markets_at_least_n(client: httpx.Client) -> None:
    resp = client.get("/api/v1/markets")
    assert resp.status_code == 200, resp.text
    markets = resp.json()
    assert len(markets) >= MIN_MARKETS, (
        f"Expected ≥{MIN_MARKETS} markets, got {len(markets)}"
    )


def test_markets_span_multiple_categories(client: httpx.Client) -> None:
    resp = client.get("/api/v1/markets")
    assert resp.status_code == 200
    categories = {m["category"] for m in resp.json()}
    assert len(categories) >= 5, f"Expected ≥5 categories, got {categories}"


def test_every_market_has_yes_price(client: httpx.Client) -> None:
    resp = client.get("/api/v1/markets")
    assert resp.status_code == 200
    for m in resp.json():
        assert m.get("yes_price") is not None, (
            f"Market {m['slug']} missing yes_price"
        )
        assert 0.0 < m["yes_price"] < 1.0, (
            f"Market {m['slug']} yes_price={m['yes_price']} out of range"
        )


def test_canonical_market_candles_non_flat(client: httpx.Client) -> None:
    resp = client.get(f"/api/v1/markets/{CANONICAL_SLUG}/candles")
    assert resp.status_code == 200, resp.text
    candles = resp.json()
    assert isinstance(candles, list), f"Expected list, got {type(candles)}"
    assert len(candles) >= MIN_SNAPSHOTS_PER_MARKET, (
        f"Expected ≥{MIN_SNAPSHOTS_PER_MARKET} candles, got {len(candles)}"
    )
    closes = [c["close"] for c in candles]
    distinct = len(set(closes))
    assert distinct > 1, f"Candle series is flat — all closes={closes[0]}"


def test_canonical_market_history_populated(client: httpx.Client) -> None:
    resp = client.get(f"/api/v1/markets/{CANONICAL_SLUG}/history?days=7")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["history"]) >= 7, (
        f"Expected ≥7 history points, got {len(body['history'])}"
    )


def test_signals_endpoint_200(client: httpx.Client) -> None:
    for path in ("/api/v1/signals", "/api/v1/signals/events", "/api/v1/signals/feed"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path}: {resp.status_code} {resp.text[:200]}"


def test_clv_endpoint_200(client: httpx.Client) -> None:
    resp = client.get(f"/api/v1/markets/{CANONICAL_SLUG}/prediction")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "predicted_prob" in data


def test_arbitrage_endpoint_200(client: httpx.Client) -> None:
    resp = client.get("/api/v1/arb/opportunities")
    assert resp.status_code == 200, resp.text


def test_portfolio_endpoint_200(client: httpx.Client) -> None:
    resp = client.get("/api/v1/portfolio/summary")
    assert resp.status_code in {200, 401}, resp.text


def test_analyst_run_produces_brief(client: httpx.Client) -> None:
    resp = client.post(f"/api/v1/analyst/run?market_slug={CANONICAL_SLUG}")
    assert resp.status_code == 200, resp.text
    brief = resp.json()
    assert brief["headline"], "Analyst produced an empty headline"
    assert brief["body_markdown"], "Analyst produced an empty body"


def test_market_detail_has_snapshot(client: httpx.Client) -> None:
    resp = client.get(f"/api/v1/markets/{CANONICAL_SLUG}/detail")
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail.get("yes_price") is not None


def test_health_endpoint_ok(client: httpx.Client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["paper_trading_only"] is True
