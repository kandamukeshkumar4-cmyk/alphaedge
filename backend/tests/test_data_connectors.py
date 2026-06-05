from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest

from app.data.connectors.kalshi import KalshiConnector, normalize_kalshi_market
from app.data.connectors.odds_api import TheOddsApiConnector, normalize_h2h_event
from app.data.connectors.onchain import OnchainReadOnlyConnector
from app.data.connectors.polymarket import PolymarketGammaConnector, normalize_gamma_market


CAPTURED_AT = datetime(2026, 1, 14, 18, tzinfo=timezone.utc)


def test_odds_api_normalizes_h2h_moneyline_payload_to_snapshots():
    snapshots = normalize_h2h_event(
        {
            "id": "nba_lal_bos_2026_01_15",
            "sport_key": "basketball_nba",
            "commence_time": "2026-01-15T00:30:00Z",
            "home_team": "Los Angeles Lakers",
            "away_team": "Boston Celtics",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "title": "DraftKings",
                    "last_update": "2026-01-14T17:59:00Z",
                    "markets": [
                        {
                            "key": "h2h",
                            "last_update": "2026-01-14T17:59:00Z",
                            "outcomes": [
                                {"name": "Los Angeles Lakers", "price": -135},
                                {"name": "Boston Celtics", "price": 115},
                            ],
                        }
                    ],
                }
            ],
        },
        captured_at=CAPTURED_AT,
    )

    assert len(snapshots) == 2
    home = snapshots[0]
    assert home.market_slug == "oddsapi:nba_lal_bos_2026_01_15:draftkings:h2h:los-angeles-lakers"
    assert home.implied_yes == pytest.approx(135 / 235)
    assert home.source == "the-odds-api:draftkings"
    assert home.book == "draftkings"
    assert home.event_id == "nba_lal_bos_2026_01_15"
    assert home.market_type == "h2h"
    assert home.outcome_name == "Los Angeles Lakers"
    assert home.captured_at == CAPTURED_AT
    assert home.close_at == datetime(2026, 1, 15, 0, 30, tzinfo=timezone.utc)
    assert home.to_odds_snapshot_record().book == "draftkings"


def test_odds_api_connector_fetches_h2h_snapshots_with_retry_and_cache():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(503, json={"message": "rebuilding"})
        return httpx.Response(
            200,
            json=[
                {
                    "id": "nba_lal_bos_2026_01_15",
                    "sport_key": "basketball_nba",
                    "commence_time": "2026-01-15T00:30:00Z",
                    "home_team": "Los Angeles Lakers",
                    "away_team": "Boston Celtics",
                    "bookmakers": [
                        {
                            "key": "draftkings",
                            "markets": [
                                {
                                    "key": "h2h",
                                    "outcomes": [
                                        {"name": "Los Angeles Lakers", "price": -135},
                                        {"name": "Boston Celtics", "price": 115},
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        )

    connector = TheOddsApiConnector(
        api_key="server-side-key",
        client=httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://api.the-odds-api.example.test",
        ),
    )

    first = connector.fetch_h2h_snapshots("basketball_nba", captured_at=CAPTURED_AT)
    second = connector.fetch_h2h_snapshots("basketball_nba", captured_at=CAPTURED_AT)

    assert first[0].market_slug.startswith("oddsapi:nba_lal_bos_2026_01_15")
    assert second == first
    assert len(requests) == 2
    assert requests[1].url.path == "/v4/sports/basketball_nba/odds"
    assert requests[1].url.params["apiKey"] == "server-side-key"
    assert requests[1].url.params["markets"] == "h2h"
    assert requests[1].url.params["oddsFormat"] == "american"


def test_odds_api_connector_fetches_historical_h2h_closing_snapshots():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "timestamp": "2026-01-15T00:25:00Z",
                "previous_timestamp": "2026-01-15T00:20:00Z",
                "next_timestamp": "2026-01-15T00:30:00Z",
                "data": [
                    {
                        "id": "nba_lal_bos_2026_01_15",
                        "sport_key": "basketball_nba",
                        "commence_time": "2026-01-15T00:30:00Z",
                        "home_team": "Los Angeles Lakers",
                        "away_team": "Boston Celtics",
                        "bookmakers": [
                            {
                                "key": "draftkings",
                                "markets": [
                                    {
                                        "key": "h2h",
                                        "outcomes": [
                                            {"name": "Los Angeles Lakers", "price": -150},
                                            {"name": "Boston Celtics", "price": 130},
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        )

    connector = TheOddsApiConnector(
        api_key="server-side-key",
        client=httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://api.the-odds-api.example.test",
        ),
    )

    snapshots = connector.fetch_historical_h2h_snapshots(
        "basketball_nba",
        snapshot_at="2026-01-15T00:30:00Z",
    )

    assert len(snapshots) == 2
    assert snapshots[0].captured_at == datetime(2026, 1, 15, 0, 25, tzinfo=timezone.utc)
    assert snapshots[0].close_at == datetime(2026, 1, 15, 0, 30, tzinfo=timezone.utc)
    assert snapshots[0].metadata["historical_snapshot_requested_at"] == (
        "2026-01-15T00:30:00Z"
    )
    assert requests[0].url.path == "/v4/historical/sports/basketball_nba/odds"
    assert requests[0].url.params["apiKey"] == "server-side-key"
    assert requests[0].url.params["regions"] == "us"
    assert requests[0].url.params["markets"] == "h2h"
    assert requests[0].url.params["oddsFormat"] == "american"
    assert requests[0].url.params["dateFormat"] == "iso"
    assert requests[0].url.params["date"] == "2026-01-15T00:30:00Z"


def test_polymarket_normalizes_gamma_market_yes_price():
    snapshot = normalize_gamma_market(
        {
            "slug": "will-lakers-beat-celtics",
            "question": "Will the Lakers beat the Celtics?",
            "category": "Sports",
            "endDate": "2026-01-15T00:30:00Z",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.5700", "0.4300"]',
            "active": True,
            "closed": False,
        },
        captured_at=CAPTURED_AT,
    )

    assert snapshot.market_slug == "polymarket:will-lakers-beat-celtics:yes"
    assert snapshot.implied_yes == pytest.approx(0.57)
    assert snapshot.source == "polymarket.gamma"
    assert snapshot.title == "Will the Lakers beat the Celtics?"
    assert snapshot.market_type == "binary"
    assert snapshot.outcome_name == "Yes"
    assert snapshot.metadata["status"] == "active"


def test_polymarket_connector_fetches_gamma_market_snapshot():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "slug": "will-lakers-beat-celtics",
                "question": "Will the Lakers beat the Celtics?",
                "outcomes": ["Yes", "No"],
                "outcomePrices": ["0.5700", "0.4300"],
                "active": True,
                "closed": False,
            },
        )

    connector = PolymarketGammaConnector(
        client=httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://gamma-api.example.test",
        )
    )

    snapshot = connector.fetch_market_snapshot("will-lakers-beat-celtics", CAPTURED_AT)

    assert snapshot.market_slug == "polymarket:will-lakers-beat-celtics:yes"
    assert snapshot.implied_yes == pytest.approx(0.57)
    assert requests[0].url.path == "/markets/slug/will-lakers-beat-celtics"


def test_kalshi_normalizes_market_midpoint_from_price_fields():
    snapshot = normalize_kalshi_market(
        {
            "market": {
                "ticker": "KXNBA-LALBOS-26JAN15",
                "title": "Lakers beat Celtics?",
                "category": "Sports",
                "status": "active",
                "close_time": "2026-01-15T00:30:00Z",
                "yes_bid_dollars": "0.5400",
                "yes_ask_dollars": "0.5800",
            }
        },
        captured_at=CAPTURED_AT,
    )

    assert snapshot.market_slug == "kalshi:kxnba-lalbos-26jan15:yes"
    assert snapshot.implied_yes == pytest.approx(0.56)
    assert snapshot.source == "kalshi.rest"
    assert snapshot.title == "Lakers beat Celtics?"
    assert snapshot.market_type == "binary"
    assert snapshot.metadata["status"] == "active"


def test_kalshi_connector_fetches_market_snapshot():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "market": {
                    "ticker": "KXNBA-LALBOS-26JAN15",
                    "title": "Lakers beat Celtics?",
                    "status": "active",
                    "last_price_dollars": "0.5700",
                }
            },
        )

    connector = KalshiConnector(
        client=httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://kalshi.example.test/trade-api/v2",
        )
    )

    snapshot = connector.fetch_market_snapshot("KXNBA-LALBOS-26JAN15", CAPTURED_AT)

    assert snapshot.market_slug == "kalshi:kxnba-lalbos-26jan15:yes"
    assert snapshot.implied_yes == pytest.approx(0.57)
    assert requests[0].url.path == "/trade-api/v2/markets/KXNBA-LALBOS-26JAN15"


def test_normalized_snapshot_converts_to_persistable_odds_record():
    snapshot = normalize_gamma_market(
        {
            "slug": "will-lakers-beat-celtics",
            "eventSlug": "nba-lal-bos",
            "question": "Will the Lakers beat the Celtics?",
            "marketType": "binary",
            "endDate": "2026-01-15T00:30:00Z",
            "outcomes": ["Yes", "No"],
            "outcomePrices": ["0.5700", "0.4300"],
            "category": "Sports",
            "active": True,
        },
        captured_at=CAPTURED_AT,
    )

    record = snapshot.to_odds_snapshot_record()

    assert record.market_slug == "polymarket:will-lakers-beat-celtics:yes"
    assert record.implied_yes == pytest.approx(0.57)
    assert record.price == pytest.approx(0.57)
    assert record.source == "polymarket.gamma"
    assert record.captured_at == CAPTURED_AT
    assert record.event_id == "nba-lal-bos"
    assert record.platform_market_id == "will-lakers-beat-celtics"
    assert record.title == "Will the Lakers beat the Celtics?"
    assert record.market_type == "binary"
    assert record.outcome_name == "Yes"
    assert record.close_at == datetime(2026, 1, 15, 0, 30, tzinfo=timezone.utc)
    assert record.metadata["category"] == "Sports"
    assert record.metadata["status"] == "active"


def test_onchain_connector_is_read_only_and_cannot_sign_or_submit_transactions():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "data": {
                    "orderFilleds": [
                        {
                            "id": "fill-1",
                            "transactionHash": "0xaaa",
                            "timestamp": "2026-01-14T17:00:00Z",
                            "wallet": "0x1111111111111111111111111111111111111111",
                            "market": "poly-lal-bos",
                            "outcome": "YES",
                            "side": "BUY",
                            "price": "0.40",
                            "quantity": "100",
                        },
                        {
                            "id": "fill-2",
                            "transactionHash": "0xbbb",
                            "timestamp": "2026-01-14T18:00:00Z",
                            "wallet": "0x1111111111111111111111111111111111111111",
                            "market": "poly-lal-bos",
                            "outcome": "YES",
                            "side": "SELL",
                            "price": "0.55",
                            "quantity": "60",
                        },
                    ]
                }
            },
        )

    connector = OnchainReadOnlyConnector(
        polygon_rpc_url="https://polygon-rpc.example.test",
        polymarket_subgraph_url="https://subgraph.example.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    public_names = {name for name in dir(connector) if not name.startswith("_")}
    assert "sign_transaction" not in public_names
    assert "send_transaction" not in public_names
    assert "private_key" not in public_names

    positions = connector.fetch_wallet_positions(
        "0x1111111111111111111111111111111111111111",
        market_prices={("poly-lal-bos", "YES"): Decimal("0.62")},
    )

    assert requests[0].method == "POST"
    assert requests[0].url == "https://subgraph.example.test"
    assert len(positions) == 1
    position = positions[0]
    assert position.wallet_address == "0x1111111111111111111111111111111111111111"
    assert position.market_id == "poly-lal-bos"
    assert position.outcome == "YES"
    assert position.side == "YES"
    assert position.quantity == Decimal("40")
    assert position.average_price == Decimal("0.4000")
    assert position.current_price == Decimal("0.6200")
    assert position.realized_pnl == Decimal("9.0000")
    assert position.unrealized_pnl == Decimal("8.8000")
    assert position.total_pnl == Decimal("17.8000")
    assert position.roi == Decimal("0.4450")
    assert position.hit_rate == Decimal("1.0000")
