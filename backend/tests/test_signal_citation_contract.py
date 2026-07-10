"""H03 — citation-consistency contract for headline-eligible signals.

``news:mispricing`` and ``anomaly:unusual_flow`` must carry a stable ``id`` and
a consistent citation shape (``news_id`` / ``news_url`` / ``headline`` /
``model_p`` / ``market_p``) so F04 can render evidence from either without
special-casing. Missing values are honest ``None`` — never fabricated.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.signals.news_mispricing import (
    CITATION_FIELDS,
    NEWS_MISPRICING_SIGNAL_TYPE,
    NewsMispricingInput,
    news_mispricing_to_events,
    stable_signal_id,
)
from app.signals.unusual_flow import (
    ANOMALY_UNUSUAL_FLOW_SIGNAL_TYPE,
    UnusualFlowInput,
    unusual_flow_to_events,
)

NOW = datetime(2026, 7, 10, 18, 0, 0, tzinfo=UTC)


def _news_events():
    item = NewsMispricingInput(
        market_slug="pm-will-lakers-beat-celtics",
        platform="polymarket",
        model_p=0.62,
        market_p=0.50,
        news_id="news-lal-injury-1",
        news_url="https://example.test/news/lal-injury",
        news_ts=NOW - timedelta(minutes=5),
        headline="Lakers star ruled out",
    )
    return news_mispricing_to_events([item], now=NOW, threshold=0.05, window_sec=900)


def _anomaly_events():
    item = UnusualFlowInput(
        market_slug="pm-will-lakers-beat-celtics",
        platform="polymarket",
        kind="price_jump",
        direction="up",
        magnitude=0.08,
        occurred_ts=NOW - timedelta(minutes=3),
        news_ts=None,  # no catalyst -> emits
        headline="",
        detail={"prev": 0.5, "curr": 0.58, "bps": 800.0},
    )
    return unusual_flow_to_events([item], window_sec=900)


def test_both_signal_types_carry_the_citation_fields():
    for events in (_news_events(), _anomaly_events()):
        assert len(events) == 1
        payload = events[0]["payload"]
        for field in CITATION_FIELDS:
            assert field in payload, f"missing citation field {field!r}"
        # id is a stable non-empty string.
        assert isinstance(payload["id"], str) and payload["id"]


def test_news_mispricing_citation_values():
    payload = _news_events()[0]["payload"]
    assert payload["signal_type"] == NEWS_MISPRICING_SIGNAL_TYPE
    assert payload["news_id"] == "news-lal-injury-1"
    assert payload["news_url"] == "https://example.test/news/lal-injury"
    assert payload["headline"] == "Lakers star ruled out"
    assert payload["model_p"] == 0.62
    assert payload["market_p"] == 0.50


def test_anomaly_citation_values_are_honest_none():
    payload = _anomaly_events()[0]["payload"]
    assert payload["signal_type"] == ANOMALY_UNUSUAL_FLOW_SIGNAL_TYPE
    # No news catalyst -> honest None, never fabricated.
    assert payload["news_id"] is None
    assert payload["news_url"] is None
    assert payload["model_p"] is None
    # market_p comes from the diff-engine detail (post-move price).
    assert payload["market_p"] == 0.58


def test_signal_id_is_deterministic_and_type_scoped():
    # Same inputs -> same id (stable across scans).
    assert _news_events()[0]["payload"]["id"] == _news_events()[0]["payload"]["id"]
    assert _anomaly_events()[0]["payload"]["id"] == _anomaly_events()[0]["payload"]["id"]
    # The two signal types never collide on the same market/instant.
    news_id = stable_signal_id(
        NEWS_MISPRICING_SIGNAL_TYPE, "pm-x", NOW, "n1"
    )
    anom_id = stable_signal_id(
        ANOMALY_UNUSUAL_FLOW_SIGNAL_TYPE, "pm-x", NOW, "price_jump"
    )
    assert news_id != anom_id
    # Naive-datetime anchors are normalised to UTC (no crash, stable value).
    assert stable_signal_id(
        NEWS_MISPRICING_SIGNAL_TYPE, "pm-x", NOW.replace(tzinfo=None), "n1"
    ) == news_id
