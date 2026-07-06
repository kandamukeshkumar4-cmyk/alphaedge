"""O04: weather edges -> delta:weather_edge SignalEvents -> feed."""

from datetime import datetime, timezone

from sqlalchemy import select

from app.api.v1.feed import _signal_to_item
from app.db.models import SignalEvent
from app.services.weather_desk import WeatherDeskService, weather_scan_to_events
from app.workers.tasks import run_weather_scan


def test_weather_desk_service_keeps_scan_city_method():
    """Guard the class structure: weather_scan_to_events must be module-level and
    must NOT displace _scan_city out of the class (a prior edit did exactly that,
    silently breaking the live scan() so the cron emitted zero events)."""
    assert hasattr(WeatherDeskService, "_scan_city")
    assert callable(WeatherDeskService.scan)

CITIES = [
    {
        "city": "New York",
        "date": "2026-07-06",
        "forecast_high_f": 88.0,
        "buckets": [
            {
                "ticker": "KXHIGHNY-26JUL06-T89",
                "bucket": "89 or above",
                "model_probability": 0.30,
                "market_yes": 0.12,
                "edge": 0.18,
                "read": "model rich",
            },
            {
                "ticker": "KXHIGHNY-26JUL06-B85",
                "bucket": "85-86",
                "model_probability": 0.10,
                "market_yes": 0.08,
                "edge": 0.02,
                "read": "fair",
            },
        ],
    },
    {
        "city": "Chicago",
        "date": "2026-07-06",
        "buckets": [  # all below the 0.10 threshold
            {"ticker": "KXHIGHCHI-26JUL06-T80", "model_probability": 0.5, "market_yes": 0.45, "edge": 0.05, "read": "fair"},
        ],
    },
    {"city": "Denver", "date": "2026-07-06", "buckets": []},
]


def test_weather_scan_to_events_takes_strongest_per_city_over_threshold():
    events = weather_scan_to_events(CITIES)
    assert len(events) == 1
    ev = events[0]
    assert ev["signal_type"] == "delta:weather_edge"
    assert ev["platform"] == "kalshi"
    assert ev["market_id"] == "KXHIGHNY-26JUL06-T89"  # strongest edge, not the T85 bucket
    assert ev["headline_eligible"] is True  # |edge| 0.18 >= 0.15
    assert ev["payload"]["paper_trading_only"] is True
    assert ev["payload"]["edge"] == 0.18


def test_weather_scan_to_events_respects_threshold_and_empty():
    # A higher threshold drops the NY edge too.
    assert weather_scan_to_events(CITIES, min_abs_edge=0.25) == []
    assert weather_scan_to_events([]) == []


def test_weather_edge_not_headline_eligible_when_small():
    cities = [
        {
            "city": "Austin",
            "buckets": [
                {"ticker": "KXHIGHAUS-x", "model_probability": 0.2, "market_yes": 0.08, "edge": 0.12, "read": "model rich"}
            ],
        }
    ]
    events = weather_scan_to_events(cities)
    assert len(events) == 1
    assert events[0]["headline_eligible"] is False  # 0.12 < 0.15


async def test_run_weather_scan_persists_signal_events(db_session):
    emitted = await run_weather_scan(db_session, CITIES)
    assert emitted == 1
    rows = (
        await db_session.execute(
            select(SignalEvent).where(SignalEvent.signal_type == "delta:weather_edge")
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].market_id == "KXHIGHNY-26JUL06-T89"
    assert rows[0].payload["city"] == "New York"


def test_weather_edge_renders_readable_feed_summary():
    ev = SignalEvent(
        signal_type="delta:weather_edge",
        platform="kalshi",
        market_id="KXHIGHNY-26JUL06-T89",
        headline_eligible=True,
        payload={
            "city": "New York",
            "model_probability": 0.30,
            "market_yes": 0.12,
            "read": "model rich",
        },
    )
    ev.created_at = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)
    item = _signal_to_item(ev, market_title=None)
    assert item.summary == "New York: model 30% vs market 12% — model rich"
