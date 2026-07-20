import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.db.models import ExternalMarket, ForecastLog, ForecastMode, Platform


@pytest.mark.asyncio
async def test_live_forecast_requires_locked_at(db_session):
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="live-lock-constraint",
        url="https://polymarket.com/event/live-lock-constraint",
        title="Live lock constraint",
    )
    db_session.add(market)
    await db_session.flush()
    forecast = ForecastLog(
        forecaster_id=__import__("uuid").uuid4(),
        external_market_id=market.id,
        platform=Platform.POLYMARKET,
        user_probability=0.6,
        mode=ForecastMode.LIVE,
    )
    db_session.add(forecast)
    await db_session.flush()
    with pytest.raises(IntegrityError):
        await db_session.execute(
            update(ForecastLog).where(ForecastLog.id == forecast.id).values(locked_at=None)
        )
    await db_session.rollback()


@pytest.mark.asyncio
async def test_practice_forecast_can_retain_legacy_null_lock(db_session):
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="practice-lock-constraint",
        url="https://polymarket.com/event/practice-lock-constraint",
        title="Practice lock constraint",
    )
    db_session.add(market)
    await db_session.flush()
    db_session.add(ForecastLog(
        forecaster_id=__import__("uuid").uuid4(),
        external_market_id=market.id,
        platform=Platform.POLYMARKET,
        user_probability=0.6,
        mode=ForecastMode.PRACTICE,
        locked_at=None,
    ))
    await db_session.flush()
