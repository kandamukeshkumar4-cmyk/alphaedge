"""C4 — scanners API (compile / create / run / pause / resume / history)."""
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

import pytest

from app.db.models import MarketSentimentSnapshot, OddsSnapshot
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService


async def _client_for(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_market(db_session):
    market = await MarketService(db_session).create_market(
        slug="nba-2025-01-15-lal-bos",
        title="Lakers vs Celtics",
        question="Will the Lakers beat the Celtics?",
        lock_at=datetime.now(UTC) + timedelta(hours=2),
        category="Sports",
        volume=50000,
    )
    db_session.add_all(
        [
            OddsSnapshot(
                market_slug=market.slug,
                implied_yes=0.48,
                captured_at=datetime.now(UTC) - timedelta(days=2),
            ),
            OddsSnapshot(
                market_slug=market.slug,
                implied_yes=0.52,
                captured_at=datetime.now(UTC),
            ),
            MarketSentimentSnapshot(
                market_slug=market.slug,
                sentiment_score=0.2,
                volume_score=0.4,
                sources_count=2,
                captured_at=datetime.now(UTC) - timedelta(hours=2),
            ),
            MarketSentimentSnapshot(
                market_slug=market.slug,
                sentiment_score=0.3,
                volume_score=0.5,
                sources_count=3,
                captured_at=datetime.now(UTC) - timedelta(hours=1),
            ),
        ]
    )
    await db_session.flush()
    return market


SPEC = {
    "name": "NBA whale trend",
    "universe": {"categories": ["nba", "sports"], "minimum_volume": 1000},
    "schedule": {"timezone": "UTC", "market_hours_only": False, "interval_minutes": 30},
    "steps": [
        {"type": "WHALE_FLOW"},
        {"type": "PRICE_TREND", "window_days": 7},
        {"type": "NEWS_SENTIMENT"},
    ],
    "delivery": {"email": False, "in_app": True, "cooldown_minutes": 120},
    "limit": 10,
}


@pytest.mark.asyncio
async def test_scanners_compile_create_run_pause_resume_history(db_session, monkeypatch):
    async def _no_network_news(topic: str, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.scanner_executor_service.fetch_news_signal", _no_network_news
    )

    await _seed_market(db_session)
    client = await _client_for(db_session)
    try:
        compiled = await client.post(
            "/api/v1/scanners/compile",
            json={
                "text": (
                    "Scan NBA sports markets every 30 minutes for whale flow and "
                    "7 day price trend with news sentiment, volume above 10000, top 10"
                )
            },
        )
        assert compiled.status_code == 200, compiled.text
        preview = compiled.json()["spec"]
        assert [s["type"] for s in preview["steps"][:3]] == [
            "WHALE_FLOW",
            "PRICE_TREND",
            "NEWS_SENTIMENT",
        ]
        assert preview["schedule"]["interval_minutes"] == 30

        signup = await client.post(
            "/api/v1/auth/signup",
            json={"email": "scanners@example.com", "password": "correct-horse-battery-staple"},
        )
        assert signup.status_code == 201
        headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

        created = await client.post(
            "/api/v1/scanners/",
            headers=headers,
            json={
                "name": "NBA whale trend",
                "description": "API fixture",
                "spec": SPEC,
                "is_public": False,
            },
        )
        assert created.status_code == 201, created.text
        scanner = created.json()
        assert scanner["status"] == "draft"
        assert scanner["owner"]
        scanner_id = scanner["id"]

        listed = await client.get("/api/v1/scanners/", headers=headers)
        assert listed.status_code == 200
        assert any(item["id"] == scanner_id for item in listed.json())

        ran = await client.post(f"/api/v1/scanners/{scanner_id}/run", headers=headers)
        assert ran.status_code == 200, ran.text
        run_body = ran.json()
        assert run_body["status"] in {"completed", "empty"}
        assert run_body["scanner_id"] == scanner_id

        detail = await client.get(f"/api/v1/scanners/{scanner_id}", headers=headers)
        assert detail.status_code == 200
        detail_body = detail.json()
        assert detail_body["latest_run"] is not None
        assert detail_body["latest_run"]["id"] == run_body["id"]
        assert detail_body["status"] == "active"
        assert "next_run_at" in detail_body
        assert detail_body["next_run_at"] is not None
        assert "last_error" in detail_body
        from datetime import UTC, datetime as _dt

        started = _dt.fromisoformat(
            detail_body["latest_run"]["started_at"].replace("Z", "+00:00")
        )
        nxt = _dt.fromisoformat(detail_body["next_run_at"].replace("Z", "+00:00"))
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        if nxt.tzinfo is None:
            nxt = nxt.replace(tzinfo=UTC)
        assert abs((nxt - started).total_seconds() - 30 * 60) < 2

        paused = await client.post(f"/api/v1/scanners/{scanner_id}/pause", headers=headers)
        assert paused.status_code == 200
        assert paused.json()["status"] == "paused"

        blocked = await client.post(f"/api/v1/scanners/{scanner_id}/run", headers=headers)
        assert blocked.status_code == 400

        resumed = await client.post(f"/api/v1/scanners/{scanner_id}/resume", headers=headers)
        assert resumed.status_code == 200
        assert resumed.json()["status"] == "active"

        # Second run for history depth
        ran2 = await client.post(f"/api/v1/scanners/{scanner_id}/run", headers=headers)
        assert ran2.status_code == 200

        history = await client.get(f"/api/v1/scanners/{scanner_id}/runs", headers=headers)
        assert history.status_code == 200
        runs = history.json()
        assert len(runs) >= 2
        assert all(r["scanner_id"] == scanner_id for r in runs)
        assert all("duration_ms" in r for r in runs)
        assert all(
            r["duration_ms"] is None or isinstance(r["duration_ms"], int) for r in runs
        )
        finished = [r for r in runs if r.get("finished_at")]
        assert finished
        assert all(
            isinstance(r["duration_ms"], int) and r["duration_ms"] >= 0 for r in finished
        )
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
