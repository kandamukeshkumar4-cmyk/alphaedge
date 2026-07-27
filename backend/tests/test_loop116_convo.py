"""Loop 116 — conversational scanner authoring (clarify → testfire → publish).

Deterministic clarification decisions only. PAPER_TRADING_ONLY — research
scanners; never touches RiskService / OrderBookService.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import MarketSentimentSnapshot, OddsSnapshot, Scanner, ScannerRun
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService
from app.services.scanner_compiler_service import (
    build_clarification_questions,
    detect_clarification_kinds,
    reset_compile_drafts,
)


@pytest.fixture(autouse=True)
def _clear_compile_drafts():
    reset_compile_drafts()
    yield
    reset_compile_drafts()


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
                captured_at=datetime.now(UTC) - timedelta(hours=1),
            ),
        ]
    )
    await db_session.flush()
    return market


@pytest.mark.asyncio
async def test_compile_missing_schedule_yields_schedule_question(db_session):
    """Missing interval → schedule clarification (deterministic)."""
    async with await _client_for(db_session) as client:
        resp = await client.post(
            "/api/v1/scanners/compile",
            json={"prompt": "Scan NBA whale flow and price trend"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "needs_clarification"
    assert body["draft_id"]
    kinds = [q["kind"] for q in body["questions"]]
    assert "schedule" in kinds
    assert len(body["questions"]) <= 3
    # Unit-level: decision function agrees.
    kinds_unit = detect_clarification_kinds(
        "Scan NBA whale flow and price trend",
        body["spec_partial"],
    )
    assert "schedule" in kinds_unit


@pytest.mark.asyncio
async def test_compile_vague_threshold_yields_threshold_question(db_session):
    """Vague quantifiers without numbers → threshold question."""
    async with await _client_for(db_session) as client:
        resp = await client.post(
            "/api/v1/scanners/compile",
            json={
                "prompt": (
                    "Watch big crypto whale flow every 30 minutes — heavy movers soon"
                )
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "needs_clarification"
    kinds = [q["kind"] for q in body["questions"]]
    assert "threshold" in kinds


@pytest.mark.asyncio
async def test_answers_roundtrip_reaches_ready(db_session):
    """Answer clarifying questions → status ready with merged spec."""
    async with await _client_for(db_session) as client:
        first = await client.post(
            "/api/v1/scanners/compile",
            json={"prompt": "Scan whale flow and price trend"},
        )
        assert first.status_code == 200, first.text
        body = first.json()
        assert body["status"] == "needs_clarification"
        draft_id = body["draft_id"]
        answers = []
        for q in body["questions"]:
            if q["kind"] == "schedule":
                answers.append(
                    {"question_id": q["id"], "answer": "Every 30 minutes"}
                )
            elif q["kind"] == "universe":
                answers.append({"question_id": q["id"], "answer": "NBA"})
            elif q["kind"] == "threshold":
                answers.append(
                    {"question_id": q["id"], "answer": "Volume above 10000"}
                )
            elif q["kind"] == "delivery":
                answers.append(
                    {"question_id": q["id"], "answer": "In-app only"}
                )
            else:
                answers.append({"question_id": q["id"], "answer": "ok"})
        second = await client.post(
            "/api/v1/scanners/compile",
            json={"prompt": "", "draft_id": draft_id, "answers": answers},
        )
    assert second.status_code == 200, second.text
    ready = second.json()
    # May still need a second round if not all kinds were in the first batch;
    # answer remaining until ready (≤2 rounds total).
    if ready["status"] == "needs_clarification":
        answers2 = []
        for q in ready["questions"]:
            if q["kind"] == "schedule":
                answers2.append(
                    {"question_id": q["id"], "answer": "Every 30 minutes"}
                )
            elif q["kind"] == "universe":
                answers2.append({"question_id": q["id"], "answer": "NBA"})
            else:
                answers2.append(
                    {"question_id": q["id"], "answer": q["suggestions"][0]}
                )
        async with await _client_for(db_session) as client:
            third = await client.post(
                "/api/v1/scanners/compile",
                json={
                    "prompt": "",
                    "draft_id": draft_id,
                    "answers": answers2,
                },
            )
        assert third.status_code == 200, third.text
        ready = third.json()
    assert ready["status"] == "ready"
    assert ready["spec"]["schedule"]["interval_minutes"] == 30
    assert "nba" in [c.lower() for c in ready["spec"]["universe"]["categories"]]


@pytest.mark.asyncio
async def test_two_rounds_max_then_best_effort_ready(db_session):
    """After two clarification rounds, force best-effort ready."""
    prompt = "Alert me about big heavy movers soon"  # schedule+threshold+universe+delivery
    async with await _client_for(db_session) as client:
        r1 = await client.post(
            "/api/v1/scanners/compile", json={"prompt": prompt}
        )
        assert r1.status_code == 200, r1.text
        b1 = r1.json()
        assert b1["status"] == "needs_clarification"
        draft_id = b1["draft_id"]
        # Non-resolving answers (no numbers / no category keywords).
        a1 = [
            {"question_id": q["id"], "answer": "later maybe"}
            for q in b1["questions"]
        ]
        r2 = await client.post(
            "/api/v1/scanners/compile",
            json={"prompt": prompt, "draft_id": draft_id, "answers": a1},
        )
        assert r2.status_code == 200, r2.text
        b2 = r2.json()
        # Second round or already best-effort ready.
        if b2["status"] == "needs_clarification":
            a2 = [
                {"question_id": q["id"], "answer": "still unsure"}
                for q in b2["questions"]
            ]
            r3 = await client.post(
                "/api/v1/scanners/compile",
                json={"prompt": prompt, "draft_id": draft_id, "answers": a2},
            )
            assert r3.status_code == 200, r3.text
            b3 = r3.json()
            assert b3["status"] == "ready"
            assert any("best-effort" in w for w in b3["warnings"])
        else:
            assert b2["status"] == "ready"


@pytest.mark.asyncio
async def test_testfire_runs_real_executor_marked_test(db_session):
    """Testfire uses real executor; run persisted with is_test=true."""
    await _seed_market(db_session)
    async with await _client_for(db_session) as client:
        compiled = await client.post(
            "/api/v1/scanners/compile",
            json={
                "prompt": (
                    "Scan NBA whale flow every 30 minutes, volume above 1000"
                )
            },
        )
        assert compiled.status_code == 200, compiled.text
        body = compiled.json()
        assert body["status"] == "ready", body
        draft_id = body["draft_id"]
        fired = await client.post(
            "/api/v1/scanners/compile/testfire",
            json={"draft_id": draft_id},
        )
    assert fired.status_code == 200, fired.text
    out = fired.json()
    assert out["draft_id"] == draft_id
    assert out["run"]["is_test"] is True
    assert out["summary"]["is_test"] is True
    assert out["summary"]["test_mode"] is True
    run_row = await db_session.scalar(
        select(ScannerRun).where(ScannerRun.id == UUID(str(out["run"]["id"])))
    )
    assert run_row is not None
    assert run_row.is_test is True
    scratch = await db_session.scalar(
        select(Scanner).where(Scanner.id == run_row.scanner_id)
    )
    assert scratch is not None
    assert scratch.owner == "__compile_draft__"
    assert scratch.is_public is False


@pytest.mark.asyncio
async def test_delivery_suggestions_never_promise_email(db_session):
    """Delivery suggestions must not promise email (flag-gated off)."""
    async with await _client_for(db_session) as client:
        resp = await client.post(
            "/api/v1/scanners/compile",
            json={
                "prompt": (
                    "Email me NBA whale flow alerts every 15 minutes, "
                    "volume above 5000"
                )
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Prompt has schedule+universe+threshold; delivery mention should trigger.
    if body["status"] == "needs_clarification":
        delivery_qs = [q for q in body["questions"] if q["kind"] == "delivery"]
        assert delivery_qs, body["questions"]
        for q in delivery_qs:
            joined = " ".join(q["suggestions"]).lower()
            assert "email" not in joined
            assert "e-mail" not in joined
            assert "inbox" not in joined
            assert "sms" not in joined
            assert "webhook" not in joined
    # Also assert the builder itself never promises email.
    qs = build_clarification_questions(["delivery"])
    assert len(qs) == 1
    joined = " ".join(qs[0]["suggestions"]).lower()
    assert "email" not in joined
    assert "inbox" not in joined
