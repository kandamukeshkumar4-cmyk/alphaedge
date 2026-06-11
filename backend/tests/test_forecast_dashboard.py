from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.db.models import SignalEvent
from app.services.forecast_dashboard_service import (
    CLVTrackingService,
    PAPER_PNL_NOTE,
    _paper_pnl_for_record,
)
from app.services.forecast_dashboard_service import CLVRecord


@pytest.mark.asyncio
async def test_get_clv_track_record_returns_resolved_records_sorted(db_session):
    db_session.add_all(
        [
            SignalEvent(
                signal_type="forecast",
                platform="polymarket",
                market_id="market-a",
                headline_eligible=True,
                payload={
                    "tracking": {
                        "resolved": True,
                        "resolved_at": "2026-01-10T12:00:00+00:00",
                        "market_slug": "market-a",
                        "model_prob": 0.62,
                        "closing_prob": 0.55,
                        "is_edge": True,
                    }
                },
            ),
            SignalEvent(
                signal_type="forecast",
                platform="polymarket",
                market_id="market-b",
                headline_eligible=False,
                payload={
                    "tracking": {
                        "resolved": True,
                        "resolved_at": "2026-01-15T12:00:00+00:00",
                        "market_slug": "market-b",
                        "model_prob": 0.48,
                        "closing_prob": 0.52,
                        "is_edge": False,
                    }
                },
            ),
            SignalEvent(
                signal_type="arbitrage",
                platform="kalshi",
                market_id="market-c",
                headline_eligible=True,
                payload={"signal": {"net_spread": 0.02}},
            ),
        ]
    )
    await db_session.flush()

    tracking = CLVTrackingService(db_session)
    records = await tracking.get_clv_track_record()

    assert len(records) == 2
    assert records[0].market_slug == "market-b"
    assert records[0].clv == pytest.approx(-0.04)
    assert records[1].market_slug == "market-a"
    assert records[1].clv == pytest.approx(0.07)
    assert records[1].is_edge is True


@pytest.mark.asyncio
async def test_get_paper_pnl_summary_has_required_keys_and_paper_only_note(db_session):
    db_session.add(
        SignalEvent(
            signal_type="forecast",
            platform="polymarket",
            market_id="market-win",
            headline_eligible=True,
            payload={
                "tracking": {
                    "resolved": True,
                    "resolved_at": datetime(2026, 1, 12, tzinfo=UTC).isoformat(),
                    "market_slug": "market-win",
                    "model_prob": 0.65,
                    "closing_prob": 0.55,
                    "is_edge": True,
                }
            },
        )
    )
    await db_session.flush()

    summary = await CLVTrackingService(db_session).get_paper_pnl_summary()

    assert summary["note"] == PAPER_PNL_NOTE
    assert summary["paper_trading_only"] is True
    assert summary["n_bets"] == 1
    assert summary["total_pnl"] == pytest.approx(10.0)
    assert summary["win_rate"] == pytest.approx(1.0)
    assert "disclaimer" in summary


def test_paper_pnl_reconciliation_math_uses_clv_times_stake():
    record = CLVRecord(
        market_slug="reconcile-test",
        model_prob=0.7,
        closing_prob=0.6,
        clv=0.1,
        resolved_at=datetime(2026, 1, 1, tzinfo=UTC),
        is_edge=True,
    )
    assert _paper_pnl_for_record(record) == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_clv_track_record_endpoint(db_session):
    from httpx import ASGITransport, AsyncClient

    from app.db.session import get_db
    from app.main import app

    db_session.add(
        SignalEvent(
            id=uuid4(),
            signal_type="forecast",
            platform="polymarket",
            market_id="endpoint-market",
            headline_eligible=True,
            payload={
                "tracking": {
                    "resolved": True,
                    "resolved_at": "2026-01-14T00:00:00+00:00",
                    "market_slug": "endpoint-market",
                    "model_prob": 0.6,
                    "closing_prob": 0.58,
                    "is_edge": False,
                }
            },
        )
    )
    await db_session.flush()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/clv-track-record")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["paper_trading_only"] is True
    assert len(body["records"]) == 1
    assert body["records"][0]["market_slug"] == "endpoint-market"
    assert body["records"][0]["clv"] == pytest.approx(0.02)


@pytest.mark.asyncio
async def test_get_clv_track_record_bounds_scan_and_limits_resolved_records(db_session):
    for index in range(15):
        db_session.add(
            SignalEvent(
                signal_type="forecast",
                platform="polymarket",
                market_id=f"bounded-{index}",
                headline_eligible=True,
                payload={
                    "tracking": {
                        "resolved": True,
                        "resolved_at": f"2026-01-{index + 1:02d}T00:00:00+00:00",
                        "market_slug": f"bounded-{index}",
                        "model_prob": 0.6,
                        "closing_prob": 0.55,
                    }
                },
            )
        )
    await db_session.flush()

    records = await CLVTrackingService(db_session).get_clv_track_record(limit=3)

    assert [record.market_slug for record in records] == [
        "bounded-14",
        "bounded-13",
        "bounded-12",
    ]
