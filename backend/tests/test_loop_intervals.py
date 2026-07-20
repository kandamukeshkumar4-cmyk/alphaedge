"""Loop V70: LOOP_INTERVALS must match app/main.py default sleeps."""

from app.core.config import get_settings
from app.observability.loop_state import LOOP_INTERVALS


def test_news_scan_interval_matches_main_five_minute_loop():
    assert LOOP_INTERVALS["news_scan"] == 300


def test_loop_intervals_match_main_default_sleeps():
    settings = get_settings()
    assert LOOP_INTERVALS["price_feed"] == 3600
    assert LOOP_INTERVALS["live_ingest"] == max(300, settings.live_ingest_interval_sec)
    assert LOOP_INTERVALS["live_tick"] == max(5, settings.live_tick_interval_sec)
    assert LOOP_INTERVALS["eval"] == 900
    assert LOOP_INTERVALS["weather_scan"] == 3600
    assert LOOP_INTERVALS["morning_research"] == 86400
    assert LOOP_INTERVALS["whale_refresh"] == 7 * 86400
    assert LOOP_INTERVALS["whale_flow"] == max(30, settings.whale_flow_interval_sec or 60)
    assert LOOP_INTERVALS["venue_gap"] == max(30, settings.venue_gap_interval_sec or 60)
    assert LOOP_INTERVALS["wc2026_resolve"] == 600
    assert LOOP_INTERVALS["external_resolve"] == 900
    assert LOOP_INTERVALS["external_market_bridge"] == 900
    assert LOOP_INTERVALS["forecast_autolock"] == 900
    assert LOOP_INTERVALS["drift_detect"] == 3600
    assert LOOP_INTERVALS["ops_alerts"] == 900
    assert LOOP_INTERVALS["portfolio_equity"] == 21600
    assert LOOP_INTERVALS["daily_digest"] == 21600
    assert LOOP_INTERVALS["jobrun_retention"] == 86400
    assert LOOP_INTERVALS["data_retention"] == 86400
    assert LOOP_INTERVALS["heartbeat_manager"] == max(
        30, settings.heartbeat_manager_interval_sec
    )
    assert LOOP_INTERVALS["pod_runner"] == 60
    # Continuous streams advertise 0 cadence.
    assert LOOP_INTERVALS["kalshi_ws"] == 0
    assert LOOP_INTERVALS["polymarket_ws"] == 0
