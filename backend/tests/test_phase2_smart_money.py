from decimal import Decimal
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from app.data.connectors.onchain import OnchainWalletPosition
from app.core.config import Settings
from app.db.models import TrackedWallet, WalletPosition
from app.db.session import get_db
from app.main import app
from app.services.wallet_service import WalletService


APP_ROOT = Path(__file__).resolve().parents[1] / "app"


async def test_smart_money_endpoint_returns_read_only_current_market_positions(db_session):
    wallet = TrackedWallet(
        wallet_address="0x1111111111111111111111111111111111111111",
        label="Fixture profitable wallet",
        realized_pnl=Decimal("9.0000"),
        unrealized_pnl=Decimal("8.8000"),
        roi=Decimal("0.4450"),
        hit_rate=Decimal("1.0000"),
        total_trades=2,
        qualified=True,
    )
    db_session.add(wallet)
    await db_session.flush()
    db_session.add(
        WalletPosition(
            tracked_wallet_id=wallet.id,
            platform="polymarket",
            market_id="poly-lal-bos",
            outcome="YES",
            side="YES",
            quantity=Decimal("40.0000"),
            average_price=Decimal("0.4000"),
            current_price=Decimal("0.6200"),
            realized_pnl=Decimal("9.0000"),
            unrealized_pnl=Decimal("8.8000"),
            total_pnl=Decimal("17.8000"),
        )
    )
    await db_session.flush()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/signals/smart-money",
                params={"platform": "polymarket", "market_id": "poly-lal-bos"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["paper_trading_only"] is True
    assert body["read_only"] is True
    assert body["platform"] == "polymarket"
    assert body["market_id"] == "poly-lal-bos"
    assert body["tracked_wallet_count"] == 1
    assert body["positions"][0]["side"] == "YES"
    assert body["positions"][0]["quantity"] == 40.0
    assert body["positions"][0]["roi"] == 0.445
    assert "No execution" in body["disclaimer"]


async def test_wallet_service_records_connector_positions_and_filters_unqualified_wallets(
    db_session,
):
    service = WalletService(db_session)

    await service.record_wallet_positions(
        "polymarket",
        [
            OnchainWalletPosition(
                wallet_address="0x1111111111111111111111111111111111111111",
                market_id="poly-lal-bos",
                outcome="YES",
                side="YES",
                quantity=Decimal("40.0000"),
                average_price=Decimal("0.4000"),
                current_price=Decimal("0.6200"),
                realized_pnl=Decimal("9.0000"),
                unrealized_pnl=Decimal("8.8000"),
                total_pnl=Decimal("17.8000"),
                roi=Decimal("0.4450"),
                hit_rate=Decimal("1.0000"),
                total_trades=2,
            ),
            OnchainWalletPosition(
                wallet_address="0x2222222222222222222222222222222222222222",
                market_id="poly-lal-bos",
                outcome="NO",
                side="NO",
                quantity=Decimal("5.0000"),
                average_price=Decimal("0.5000"),
                current_price=Decimal("0.5100"),
                realized_pnl=Decimal("0.0000"),
                unrealized_pnl=Decimal("0.0500"),
                total_pnl=Decimal("0.0500"),
                roi=Decimal("0.0200"),
                hit_rate=Decimal("1.0000"),
                total_trades=1,
            ),
        ],
    )
    await db_session.flush()

    payload = await service.smart_money_signal("polymarket", "poly-lal-bos")

    assert payload["tracked_wallet_count"] == 1
    assert payload["positions"][0]["wallet_address"] == (
        "0x1111111111111111111111111111111111111111"
    )
    assert payload["positions"][0]["side"] == "YES"


def test_smart_money_backend_has_no_private_key_or_signing_code():
    forbidden = ("private_key", "sign_transaction", "send_transaction", "mnemonic")
    for path in APP_ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in source, f"{token} appeared in {path.relative_to(APP_ROOT)}"


def test_phase2_settings_expose_read_only_onchain_sources():
    settings = Settings(
        POLYGON_RPC_URL="https://polygon-rpc.example.test",
        POLYMARKET_SUBGRAPH_URL="https://subgraph.example.test",
        TRACKED_WALLET_ADDRESSES=(
            "0x1111111111111111111111111111111111111111,"
            "0x2222222222222222222222222222222222222222"
        ),
    )

    assert settings.polygon_rpc_url == "https://polygon-rpc.example.test"
    assert settings.polymarket_subgraph_url == "https://subgraph.example.test"
    assert settings.tracked_wallet_address_list == [
        "0x1111111111111111111111111111111111111111",
        "0x2222222222222222222222222222222222222222",
    ]
