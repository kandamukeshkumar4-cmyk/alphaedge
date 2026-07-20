"""Loop V70: shared CircuitBreaker + TtlLruCache."""

from app.core.resilience import CircuitBreaker, TtlLruCache


def test_circuit_opens_after_threshold_and_closes_after_cooldown():
    br = CircuitBreaker(failure_threshold=3, cooldown_sec=10.0)
    assert br.is_open(now=0.0) is False
    br.record_failure(now=1.0)
    br.record_failure(now=2.0)
    assert br.is_open(now=3.0) is False
    br.record_failure(now=3.0)
    assert br.is_open(now=4.0) is True
    assert br.is_open(now=12.9) is True
    assert br.is_open(now=13.0) is False  # cooldown elapsed
    br.record_success()
    assert br.consecutive_failures == 0


def test_ttl_lru_age_gated_reads_and_eviction():
    cache: TtlLruCache[str, int] = TtlLruCache(maxsize=2, ttl_sec=10.0)
    cache.set("a", 1, now=0.0)
    cache.set("b", 2, now=1.0)
    assert cache.get("a", now=5.0) == 1
    # Insert c → evict least-recently-used ("b" was not touched after a get)
    cache.set("c", 3, now=6.0)
    assert cache.get("b", now=6.0) is None
    assert cache.get("a", now=6.0) == 1
    assert cache.get("c", now=6.0) == 3
    # TTL expiry
    assert cache.get("a", now=16.1) is None
    assert len(cache) == 1  # only c left after a expired on read


def test_signal_modules_use_shared_breaker_and_bounded_cache():
    from app.signals import news_cadence, nemotron_signal, venue_gap, whale_flow
    from app.core.resilience import CircuitBreaker, TtlLruCache

    assert isinstance(whale_flow._breaker, CircuitBreaker)
    assert isinstance(whale_flow._PRESSURE_CACHE, TtlLruCache)
    assert whale_flow._PRESSURE_CACHE.maxsize == 2048

    assert isinstance(venue_gap._breaker, CircuitBreaker)
    assert isinstance(venue_gap._GAP_CACHE, TtlLruCache)
    assert venue_gap._GAP_CACHE.maxsize == 2048

    assert isinstance(nemotron_signal._breaker, CircuitBreaker)
    assert isinstance(nemotron_signal._CACHE, TtlLruCache)
    assert nemotron_signal._CACHE.maxsize == 2048

    assert isinstance(news_cadence._breaker, CircuitBreaker)
    assert isinstance(news_cadence._last_refresh, TtlLruCache)
    assert news_cadence._last_refresh.maxsize == 2048
