from collections.abc import Iterator

import httpx
import pytest

CANONICAL_SLUG = "nba-2025-01-15-lal-bos"


@pytest.fixture
def client(base_url: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=base_url, timeout=30.0) as http_client:
        yield http_client


def test_health(client: httpx.Client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data.get("paper_trading_only") is True or data.get("paper_trading") is True


def test_markets_list_includes_resolution_outcome(client: httpx.Client) -> None:
    response = client.get("/api/v1/markets")
    assert response.status_code == 200
    markets = response.json()
    assert isinstance(markets, list)
    assert markets, "Expected at least one public market"
    for market in markets:
        assert "resolution_outcome" in market


def test_leaderboard_response_shape(client: httpx.Client) -> None:
    response = client.get("/api/v1/leaderboard")
    assert response.status_code == 200
    data = response.json()
    assert "entries" in data
    assert isinstance(data["entries"], list)
    for entry in data["entries"]:
        assert isinstance(entry["rank"], int)
        assert isinstance(entry["username"], str)
        assert isinstance(entry["realized_pnl"], (int, float))
        assert isinstance(entry["total_trades"], int)
        assert isinstance(entry["win_rate"], (int, float))


def test_orders_post_auth_required_not_server_error(client: httpx.Client) -> None:
    response = client.post(
        "/api/v1/orders",
        json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.5},
    )
    assert response.status_code in {200, 201, 401, 422}
    assert response.status_code != 500
