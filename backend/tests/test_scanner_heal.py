"""H1/H2/H3 — scanner self-heal classifier, repairs, and API visibility."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.db.models import OddsSnapshot, Scanner
from app.services.market_service import MarketService
from app.services.scanner_executor_service import run_scanner
from app.services.scanner_heal_service import (
    EmptyResponseError,
    classify_step_error,
    coerce_numeric_strings,
)


@pytest.mark.parametrize(
    "exc,expected",
    [
        (ValueError("could not convert string to float: 'x'"), "type_mismatch"),
        (TypeError("int() argument must be a string, not 'list'"), "type_mismatch"),
        (KeyError("pressure"), "missing_field"),
        (AttributeError("'NoneType' object has no attribute 'yes_price'"), "missing_field"),
        (EmptyResponseError([]), "empty_response"),
        (ValueError("empty list"), "empty_response"),
        (RuntimeError("HTTP 429 rate limit exceeded"), "rate_limited"),
        (RuntimeError("provider rate exceeded"), "rate_limited"),
        (LookupError("404 market slug nba-2025-01-15-lal-bos not found"), "invalid_market"),
        (RuntimeError("market locked: lock_at in the past"), "expired_market"),
        (TimeoutError("upstream timeout after 30s"), "provider_transient"),
        (RuntimeError("HTTP 503 temporarily unavailable"), "provider_transient"),
        (RuntimeError("something completely unexpected"), "unknown"),
    ],
)
def test_classify_step_error_eight_classes(exc, expected):
    assert classify_step_error(exc, context={"node": 0}) == expected


def test_classify_covers_all_eight_distinct_classes():
    samples = {
        "type_mismatch": ValueError("invalid literal for int() with base 10"),
        "missing_field": KeyError("reads"),
        "empty_response": EmptyResponseError("[]"),
        "rate_limited": Exception("429 Too Many Requests"),
        "invalid_market": Exception("slug=nba-bad-slug not found"),
        "expired_market": Exception("market closed in the past"),
        "provider_transient": Exception("502 Bad Gateway"),
        "unknown": Exception("no idea"),
    }
    got = {classify_step_error(e) for e in samples.values()}
    assert got == set(samples.keys())


def test_coerce_numeric_strings_guarded():
    assert coerce_numeric_strings({"window_days": "7", "name": "x"}) == {
        "window_days": 7.0,
        "name": "x",
    }
    assert coerce_numeric_strings(["1.5", "nope"]) == [1.5, "nope"]


async def _seed_one_market(db_session):
    market = await MarketService(db_session).create_market(
        slug="nba-2025-01-15-lal-bos",
        title="Lakers vs Celtics",
        question="Will the Lakers beat the Celtics?",
        lock_at=datetime.now(UTC) + timedelta(hours=2),
        category="Sports",
        volume=50000,
    )
    db_session.add(
        OddsSnapshot(
            market_slug=market.slug,
            implied_yes=0.5,
            captured_at=datetime.now(UTC),
        )
    )
    await db_session.flush()
    return market


def _minimal_scanner(**spec_extra) -> Scanner:
    spec = {
        "name": "heal-fixture",
        "universe": {"categories": ["sports"], "minimum_volume": 1},
        "schedule": {
            "timezone": "UTC",
            "market_hours_only": False,
            "interval_minutes": 60,
        },
        "steps": [{"type": "WHALE_FLOW"}],
        "delivery": {"email": False, "in_app": True, "cooldown_minutes": 120},
        "limit": 5,
    }
    spec.update(spec_extra)
    return Scanner(name="heal-fixture", owner="tester", spec=spec, status="active")


@pytest.mark.asyncio
async def test_type_mismatch_step_heals_and_completes(db_session, monkeypatch):
    await _seed_one_market(db_session)
    calls = {"n": 0}

    async def _flaky(db, step, candidates, *, align_present):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("could not convert string to float: '7'")
        return list(candidates)

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(
        "app.services.scanner_executor_service._run_step", _flaky
    )
    monkeypatch.setattr(
        "app.services.scanner_executor_service._heal_sleep", _no_sleep
    )

    scanner = _minimal_scanner()
    db_session.add(scanner)
    await db_session.flush()

    run = await run_scanner(db_session, scanner)
    assert run.status == "completed"
    assert calls["n"] == 2
    repairs = (run.result or {}).get("repairs") or []
    assert repairs == [
        {"node": 0, "class": "type_mismatch", "action": "coerce_numeric"}
    ]


@pytest.mark.asyncio
async def test_unknown_error_propagates_to_failed(db_session, monkeypatch):
    await _seed_one_market(db_session)

    async def _boom(db, step, candidates, *, align_present):
        raise RuntimeError("completely weird failure")

    monkeypatch.setattr(
        "app.services.scanner_executor_service._run_step", _boom
    )

    scanner = _minimal_scanner()
    db_session.add(scanner)
    await db_session.flush()

    run = await run_scanner(db_session, scanner)
    assert run.status == "failed"
    assert "weird" in (run.error or "")
    assert not (run.result or {}).get("repairs")


@pytest.mark.asyncio
async def test_invalid_market_drop_records_counts_dropped(db_session, monkeypatch):
    await _seed_one_market(db_session)
    calls = {"n": 0}

    async def _bad_slug(db, step, candidates, *, align_present):
        calls["n"] += 1
        if calls["n"] == 1:
            raise LookupError("404 market slug nba-2025-01-15-lal-bos not found")
        return list(candidates)

    monkeypatch.setattr(
        "app.services.scanner_executor_service._run_step", _bad_slug
    )

    scanner = _minimal_scanner()
    db_session.add(scanner)
    await db_session.flush()

    run = await run_scanner(db_session, scanner)
    # All markets dropped → empty candidates → status empty
    assert run.status == "empty"
    result = run.result or {}
    assert result["counts"]["dropped"] == 1
    assert result["repairs"] == [
        {"node": 0, "class": "invalid_market", "action": "drop_market"}
    ]
    assert result["candidates"] == []


@pytest.mark.asyncio
async def test_runs_api_includes_repairs_count_and_list(db_session, monkeypatch):
    """H3 — GET /{id}/runs exposes repairs_count; payload includes repairs list."""
    from httpx import ASGITransport, AsyncClient

    from app.db.session import get_db
    from app.main import app

    await _seed_one_market(db_session)
    calls = {"n": 0}

    async def _flaky(db, step, candidates, *, align_present):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("could not convert string to float: '7'")
        return list(candidates)

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(
        "app.services.scanner_executor_service._run_step", _flaky
    )
    monkeypatch.setattr(
        "app.services.scanner_executor_service._heal_sleep", _no_sleep
    )

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        signup = await client.post(
            "/api/v1/auth/signup",
            json={
                "email": "scanner-heal@example.com",
                "password": "correct-horse-battery-staple",
            },
        )
        assert signup.status_code == 201, signup.text
        headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

        created = await client.post(
            "/api/v1/scanners/",
            headers=headers,
            json={
                "name": "heal-api",
                "description": "h3",
                "spec": {
                    "name": "heal-api",
                    "universe": {"categories": ["sports"], "minimum_volume": 1},
                    "schedule": {
                        "timezone": "UTC",
                        "market_hours_only": False,
                        "interval_minutes": 60,
                    },
                    "steps": [{"type": "WHALE_FLOW"}],
                    "delivery": {
                        "email": False,
                        "in_app": True,
                        "cooldown_minutes": 120,
                    },
                    "limit": 5,
                },
                "is_public": True,
            },
        )
        assert created.status_code == 201, created.text
        scanner_id = created.json()["id"]

        ran = await client.post(
            f"/api/v1/scanners/{scanner_id}/run", headers=headers
        )
        assert ran.status_code == 200, ran.text
        body = ran.json()
        assert body["status"] == "completed"
        assert body["repairs_count"] == 1
        assert body["repairs"] == [
            {"node": 0, "class": "type_mismatch", "action": "coerce_numeric"}
        ]
        # Detail panel also sees repairs inside result.
        assert (body.get("result") or {}).get("repairs") == body["repairs"]

        history = await client.get(
            f"/api/v1/scanners/{scanner_id}/runs", headers=headers
        )
        assert history.status_code == 200, history.text
        items = history.json()
        assert len(items) >= 1
        assert items[0]["repairs_count"] == 1
        assert items[0]["repairs"][0]["class"] == "type_mismatch"

        detail = await client.get(
            f"/api/v1/scanners/{scanner_id}", headers=headers
        )
        assert detail.status_code == 200, detail.text
        latest = detail.json().get("latest_run") or {}
        assert latest.get("repairs_count") == 1
        assert latest.get("repairs") == body["repairs"]
    finally:
        await client.aclose()
        app.dependency_overrides.pop(get_db, None)
