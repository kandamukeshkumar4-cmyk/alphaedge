"""Loop V61 S1 adaptive news cadence tests."""

from datetime import UTC, datetime, timedelta

from app.signals.news_cadence import (
    BASELINE_INTERVAL_SEC,
    HOT_INTERVAL_SEC,
    WARM_INTERVAL_SEC,
    NewsRefreshCandidate,
    circuit_is_open,
    eligible_candidates,
    record_refresh_failure,
    record_refresh_success,
    refresh_interval_sec,
    reset_news_cadence_state,
)


def _candidate(**changes) -> NewsRefreshCandidate:
    data = {
        "slug": "m1",
        "close_at": None,
        "price_delta_1h": None,
        "whale_pressure": None,
        "volume": 1,
    }
    data.update(changes)
    return NewsRefreshCandidate(**data)


def test_cadence_is_hot_for_close_price_or_whale_and_hourly_elsewhere():
    now = datetime(2026, 7, 17, 12, tzinfo=UTC)
    assert refresh_interval_sec(_candidate(close_at=now + timedelta(minutes=10)), now=now) == HOT_INTERVAL_SEC
    assert refresh_interval_sec(_candidate(price_delta_1h=-0.05), now=now) == HOT_INTERVAL_SEC
    assert refresh_interval_sec(_candidate(whale_pressure=0.5), now=now) == HOT_INTERVAL_SEC
    assert refresh_interval_sec(_candidate(close_at=now + timedelta(minutes=90)), now=now) == WARM_INTERVAL_SEC
    assert refresh_interval_sec(_candidate(), now=now) == BASELINE_INTERVAL_SEC


def test_cadence_budget_prioritizes_hot_and_suppresses_recent_refreshes():
    reset_news_cadence_state()
    now = datetime(2026, 7, 17, 12, tzinfo=UTC)
    hot = _candidate(slug="hot", whale_pressure=0.9, volume=1)
    baseline = _candidate(slug="baseline", volume=100)
    assert [c.slug for c in eligible_candidates([baseline, hot], now=now, budget=1, monotonic_now=1000)] == ["hot"]
    record_refresh_success("hot", monotonic_now=1000)
    assert eligible_candidates([hot], now=now, budget=1, monotonic_now=1001) == []


def test_cadence_thresholds_are_configurable():
    reset_news_cadence_state()
    now = datetime(2026, 7, 17, 12, tzinfo=UTC)
    candidate = _candidate(slug="custom", price_delta_1h=0.02)
    assert eligible_candidates(
        [_candidate(slug="baseline", volume=100), candidate],
        now=now,
        budget=1,
        price_jump_threshold=0.01,
        monotonic_now=1000,
    ) == [candidate]


def test_cadence_circuit_opens_after_three_fetch_failures():
    reset_news_cadence_state()
    try:
        for _ in range(3):
            record_refresh_failure(monotonic_now=10)
        assert circuit_is_open(monotonic_now=11) is True
        assert eligible_candidates([_candidate()], now=datetime.now(UTC), budget=10, monotonic_now=11) == []
    finally:
        # The circuit is keyed to real time.monotonic() (~system uptime). On a
        # freshly booted CI runner that clock is still below the fake
        # `10 + COOLDOWN_SEC` threshold, so a leaked open circuit silently
        # disables run_news_scan in later tests (test_news_signal B04).
        reset_news_cadence_state()
