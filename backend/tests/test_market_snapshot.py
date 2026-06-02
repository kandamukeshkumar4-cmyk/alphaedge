from datetime import datetime, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import (
    Account,
    Evaluation,
    OrderOutcome,
    OrderSide,
    OrderType,
    PredictionLog,
)
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService


@pytest.mark.asyncio
async def test_market_snapshot_includes_book_activity_forecast_and_eval_proof(db_session):
    market_service = MarketService(db_session)
    order_book = OrderBookService(db_session)
    market = await market_service.create_market(
        slug="nba-2025-01-15-lal-bos",
        title="Lakers vs Celtics",
        question="Will the Lakers win?",
        lock_at=datetime(2025, 1, 15, 19, 30, tzinfo=timezone.utc),
    )

    maker = Account(name="Maker", cash_balance=Decimal("5000"))
    taker = Account(name="Taker", cash_balance=Decimal("5000"))
    db_session.add_all([maker, taker])
    await db_session.flush()

    await order_book.submit_order(
        market.id,
        maker.id,
        OrderSide.SELL,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("40"),
        Decimal("0.64"),
    )
    await order_book.submit_order(
        market.id,
        maker.id,
        OrderSide.BUY,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("20"),
        Decimal("0.60"),
    )
    await order_book.submit_order(
        market.id,
        taker.id,
        OrderSide.BUY,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("10"),
        Decimal("0.64"),
    )

    db_session.add(
        PredictionLog(
            market_id=market.id,
            market_slug=market.slug,
            predicted_prob=Decimal("0.6800"),
            confidence=Decimal("0.8400"),
            input_feature_hash="fixture-v1",
        )
    )
    db_session.add(
        Evaluation(
            market_id=market.id,
            brier_score=Decimal("0.102400"),
            predicted_prob=Decimal("0.6800"),
            actual_outcome=1,
            closing_implied=Decimal("0.6400"),
        )
    )
    await db_session.flush()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/markets/nba-2025-01-15-lal-bos/snapshot")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["paper_trading_only"] is True
    assert "paper-trading simulation" in payload["disclaimer"]
    assert payload["market"]["slug"] == "nba-2025-01-15-lal-bos"
    assert payload["book"]["yes"]["bids"][0] == {"price": 0.6, "size": 20.0}
    assert payload["book"]["yes"]["asks"][0] == {"price": 0.64, "size": 30.0}
    assert payload["activity"][0]["outcome"] == "yes"
    assert payload["activity"][0]["price"] == 0.64
    assert payload["activity"][0]["quantity"] == 10.0
    assert payload["forecast"] == {
        "predicted_prob": 0.68,
        "confidence": 0.84,
        "edge_vs_book": 0.04,
        "input_feature_hash": "fixture-v1",
    }
    assert payload["evaluation"] == {
        "latest_brier_score": 0.1024,
        "predicted_prob": 0.68,
        "actual_outcome": 1,
        "closing_implied": 0.64,
    }
