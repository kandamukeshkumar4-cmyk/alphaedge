"""Loop V61 S1 adaptive news cadence tests."""

from datetime import UTC, datetime, timedelta

from app.signals.news_cadence import (
    BASELINE_INTERVAL_SEC,
    FALLBACK_COOLDOWN_SEC,
    HOT_INTERVAL_SEC,
    WARM_INTERVAL_SEC,
    NewsRefreshCandidate,
    circuit_is_open,
    eligible_candidates,
    fallback_eligible_candidates,
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
    for _ in range(3):
        record_refresh_failure(monotonic_now=10)
    assert circuit_is_open(monotonic_now=11) is True
    assert eligible_candidates([_candidate()], now=datetime.now(UTC), budget=10, monotonic_now=11) == []


def test_fallback_flag_off_enforces_60min_per_slug_cooldown():
    """NEWS_CADENCE_ENABLED=false must not 12x hourly volume on a 5-min loop."""
    reset_news_cadence_state()
    assert FALLBACK_COOLDOWN_SEC == BASELINE_INTERVAL_SEC == 3600
    cands = [
        _candidate(slug="a", volume=100),
        _candidate(slug="b", volume=50),
        _candidate(slug="c", volume=10),
    ]
    first = fallback_eligible_candidates(cands, budget=2, monotonic_now=1000.0)
    assert [c.slug for c in first] == ["a", "b"]
    record_refresh_success("a", monotonic_now=1000.0)
    record_refresh_success("b", monotonic_now=1000.0)
    # 5 minutes later: a/b still cooling; c was never refreshed so it is due.
    second = fallback_eligible_candidates(cands, budget=2, monotonic_now=1000.0 + 300)
    assert [c.slug for c in second] == ["c"]
    record_refresh_success("c", monotonic_now=1000.0 + 300)
    # Still within cooldown for everyone.
    assert (
        fallback_eligible_candidates(cands, budget=3, monotonic_now=1000.0 + 600) == []
    )
    # After full hour from a/b refresh: a/b due; c still within its own cooldown.
    third = fallback_eligible_candidates(
        cands, budget=3, monotonic_now=1000.0 + FALLBACK_COOLDOWN_SEC
    )
    assert [c.slug for c in third] == ["a", "b"]
    # After full hour from c's refresh: all due again in input order.
    fourth = fallback_eligible_candidates(
        cands, budget=3, monotonic_now=1000.0 + 300 + FALLBACK_COOLDOWN_SEC
    )
    assert [c.slug for c in fourth] == ["a", "b", "c"]
