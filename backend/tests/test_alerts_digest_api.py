"""L02 — alerts digest tests (read-only composition of signal_events).

Public GET. Per-family counts + top-N most-alerted markets over a bounded
window. Honest empty; never fabricates data or a price move.
"""
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import Market, MarketStatus, SignalEvent
from app.db.session import get_db
from app.main import app

SLUG_A = "nba-2025-01-15-lal-bos"
SLUG_B = "nba-2025-01-16-gsw-mia"


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _get(path: str):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path)


async def _seed(db_session) -> None:
    now = datetime.now(UTC)
    db_session.add_all(
        [
            Market(slug=SLUG_A, title="A", question="A?", status=MarketStatus.OPEN),
            Market(slug=SLUG_B, title="B", question="B?", status=MarketStatus.OPEN),
        ]
    )
    await db_session.flush()
    db_session.add_all(
        [
            # SLUG_A: 3 alert-family events (2 delta:* collapse into one family).
            SignalEvent(
                signal_type="news:mispricing",
                platform="seed",
                market_id=SLUG_A,
                payload={},
                created_at=now - timedelta(hours=1),
            ),
            SignalEvent(
                signal_type="delta:price_jump",
                platform="stream",
                market_id=SLUG_A,
                payload={},
                created_at=now - timedelta(hours=2),
            ),
            SignalEvent(
                signal_type="delta:vol_spike",
                platform="stream",
                market_id=SLUG_A,
                payload={},
                created_at=now - timedelta(hours=3),
            ),
            # SLUG_B: 1 alert-family event.
            SignalEvent(
                signal_type="arb",
                platform="seed",
                market_id=SLUG_B,
                payload={},
                created_at=now - timedelta(hours=1),
            ),
            # Outside a 24h window (old) — must be excluded by window filter.
            SignalEvent(
                signal_type="screener:momentum",
                platform="seed",
                market_id=SLUG_B,
                payload={},
                created_at=now - timedelta(days=3),
            ),
            # NON-family event: must never count.
            SignalEvent(
                signal_type="alignment",
                platform="seed",
                market_id=SLUG_A,
                payload={},
                created_at=now - timedelta(minutes=30),
            ),
        ]
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_family_counts_and_window(db_session):
    await _seed(db_session)
    body = (await _get("/api/v1/alerts/digest?window=24h")).json()
    assert body["window"] == "24h"
    assert body["window_hours"] == 24
    # 24h window: news:mispricing(1) + delta:*(2) + arb(1) = 4; alignment excluded,
    # the 3-days-old screener event excluded.
    assert body["families"] == {"news:mispricing": 1, "delta:*": 2, "arb": 1}
    assert body["total"] == 4
    assert "screener:*" not in body["families"]


@pytest.mark.asyncio
async def test_wider_window_includes_older_events(db_session):
    await _seed(db_session)
    body = (await _get("/api/v1/alerts/digest?window=7d")).json()
    assert body["window"] == "7d"
    assert body["window_hours"] == 168
    # 7d window now also sees the 3-days-old screener:momentum event.
    assert body["families"].get("screener:*") == 1
    assert body["total"] == 5


@pytest.mark.asyncio
async def test_top_movers_ordering(db_session):
    await _seed(db_session)
    body = (await _get("/api/v1/alerts/digest?window=24h")).json()
    movers = body["top_movers"]
    # SLUG_A (3 signals) ranks above SLUG_B (1 signal).
    assert [m["slug"] for m in movers] == [SLUG_A, SLUG_B]
    assert movers[0]["signal_count"] == 3
    assert movers[0]["families"] == {"news:mispricing": 1, "delta:*": 2}
    assert movers[1]["signal_count"] == 1


@pytest.mark.asyncio
async def test_slug_filter(db_session):
    await _seed(db_session)
    body = (await _get(f"/api/v1/alerts/digest?window=24h&slugs={SLUG_B}")).json()
    assert body["families"] == {"arb": 1}
    assert [m["slug"] for m in body["top_movers"]] == [SLUG_B]
    assert body["total"] == 1


@pytest.mark.asyncio
async def test_honest_empty(db_session):
    # No signal events seeded at all.
    body = (await _get("/api/v1/alerts/digest?window=24h")).json()
    assert body["families"] == {}
    assert body["top_movers"] == []
    assert body["total"] == 0
    assert body["window"] == "24h"


@pytest.mark.asyncio
async def test_default_and_invalid_window_fall_back_to_24h(db_session):
    await _seed(db_session)
    default = (await _get("/api/v1/alerts/digest")).json()
    assert default["window"] == "24h"
    assert default["window_hours"] == 24
    # Garbage window is lenient (never 422/5xx) → default 24h.
    garbage = (await _get("/api/v1/alerts/digest?window=notawindow")).json()
    assert garbage["window_hours"] == 24
    # Out-of-range window clamps to the 30d max.
    huge = (await _get("/api/v1/alerts/digest?window=999d")).json()
    assert huge["window_hours"] == 30 * 24
