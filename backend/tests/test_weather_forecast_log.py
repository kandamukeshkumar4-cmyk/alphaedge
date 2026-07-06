"""O05: weather forecast-vs-actual logging + learned-sigma bootstrap."""

from datetime import date, timezone
from datetime import datetime as dt

from sqlalchemy import func, select

from app.db.models import WeatherForecastLog
from app.services.weather_desk import suggest_sigma_f
from app.workers.tasks import log_weather_forecasts, record_weather_actuals

DAY = date(2026, 7, 7)
CITIES = [
    {"city": "New York", "date": DAY.isoformat(), "forecast_high_f": 88.0, "sigma_f": 4.0, "source": "nws.point-forecast"},
    {"city": "Chicago", "date": DAY.isoformat(), "forecast_high_f": 79.0, "sigma_f": 4.0},
    {"city": "NoForecast", "date": DAY.isoformat(), "forecast_high_f": None},  # skipped
]


# ── suggest_sigma_f (pure) ───────────────────────────────────────────────────


def test_suggest_sigma_none_below_min_pairs():
    assert suggest_sigma_f([(80.0, 82.0)], min_pairs=30) is None


def test_suggest_sigma_is_rms_error():
    # errors of -2 and +2 over 4 pairs → RMS = 2.0
    pairs = [(80.0, 82.0), (80.0, 78.0), (70.0, 72.0), (70.0, 68.0)]
    assert suggest_sigma_f(pairs, min_pairs=4) == 2.0


def test_suggest_sigma_zero_when_perfect():
    pairs = [(80.0, 80.0)] * 5
    assert suggest_sigma_f(pairs, min_pairs=5) == 0.0


# ── log_weather_forecasts (upsert) ───────────────────────────────────────────


async def test_log_weather_forecasts_inserts_one_row_per_city(db_session):
    logged = await log_weather_forecasts(db_session, CITIES, DAY)
    assert logged == 2  # NoForecast skipped
    rows = (await db_session.execute(select(WeatherForecastLog))).scalars().all()
    assert {r.city for r in rows} == {"New York", "Chicago"}
    ny = next(r for r in rows if r.city == "New York")
    assert float(ny.forecast_high_f) == 88.0
    assert float(ny.sigma_used) == 4.0
    assert ny.actual_high_f is None


async def test_log_weather_forecasts_upserts_same_day(db_session):
    await log_weather_forecasts(db_session, CITIES, DAY)
    # Re-scan with a revised forecast — must UPDATE, not duplicate.
    revised = [{"city": "New York", "date": DAY.isoformat(), "forecast_high_f": 90.0, "sigma_f": 3.5}]
    await log_weather_forecasts(db_session, revised, DAY)
    count = (
        await db_session.execute(
            select(func.count()).select_from(WeatherForecastLog).where(
                WeatherForecastLog.city == "New York"
            )
        )
    ).scalar_one()
    assert count == 1
    row = await db_session.scalar(
        select(WeatherForecastLog).where(WeatherForecastLog.city == "New York")
    )
    assert float(row.forecast_high_f) == 90.0
    assert float(row.sigma_used) == 3.5


# ── record_weather_actuals (fill) ────────────────────────────────────────────


async def test_record_weather_actuals_fills_and_is_idempotent(db_session):
    await log_weather_forecasts(db_session, CITIES, DAY)
    now = dt(2026, 7, 8, 6, 0, tzinfo=timezone.utc)
    resolved = await record_weather_actuals(
        db_session,
        {("New York", DAY): 86.0, ("Chicago", DAY): 81.0},
        now=now,
    )
    assert resolved == 2
    ny = await db_session.scalar(
        select(WeatherForecastLog).where(WeatherForecastLog.city == "New York")
    )
    assert float(ny.actual_high_f) == 86.0
    assert ny.resolved_at is not None

    # Second pass with the same actuals must not re-resolve (idempotent).
    again = await record_weather_actuals(db_session, {("New York", DAY): 99.0}, now=now)
    assert again == 0
    ny2 = await db_session.scalar(
        select(WeatherForecastLog).where(WeatherForecastLog.city == "New York")
    )
    assert float(ny2.actual_high_f) == 86.0  # unchanged
