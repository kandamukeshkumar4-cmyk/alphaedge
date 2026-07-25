"""N01 — Opportunity scanner tests (Loop V9).

``GET /api/v1/opportunities`` — PUBLIC GET. Ranked read-only view of markets by
absolute model-vs-market edge |model_p − market_p|, with a liquidity floor and
optional direction filter. Markets with NO model probability are EXCLUDED
honestly (never faked); honest empty on no data.
"""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import opportunities_cache
from app.db.models import (
    Market,
    MarketStatus,
    OddsSnapshot,
    PredictionLog,
    SignalEvent,
)
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    opportunities_cache.invalidate()
    yield
    app.dependency_overrides.clear()
    opportunities_cache.invalidate()


async def _get(path: str):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path)


async def _add_market(
    db_session,
    slug: str,
    *,
    volume: int,
    model_p: float | None,
    yes_price: float | None,
) -> None:
    now = datetime.now(UTC)
    db_session.add(
        Market(
            slug=slug,
            title=f"Market {slug}",
            question="?",
            status=MarketStatus.OPEN,
            volume=volume,
        )
    )
    await db_session.flush()
    if yes_price is not None:
        db_session.add(
            OddsSnapshot(
                market_slug=slug,
                implied_yes=Decimal(str(yes_price)),
                source="seed",
                captured_at=now - timedelta(minutes=5),
            )
        )
    if model_p is not None:
        db_session.add(
            PredictionLog(
                market_slug=slug,
                predicted_prob=Decimal(str(model_p)),
                confidence=Decimal("0.7"),
                predicted_at=now - timedelta(hours=1),
            )
        )
    await db_session.flush()


async def _seed(db_session) -> None:
    # edge 0.30, YES lean, high liquidity
    await _add_market(db_session, "big-edge", volume=5000, model_p=0.80, yes_price=0.50)
    # edge 0.05, YES lean
    await _add_market(db_session, "small-edge", volume=8000, model_p=0.55, yes_price=0.50)
    # edge 0.40, YES lean, but tiny liquidity (floor test)
    await _add_market(db_session, "low-liq", volume=100, model_p=0.90, yes_price=0.50)
    # edge 0.20, NO lean (direction filter)
    await _add_market(db_session, "no-lean", volume=3000, model_p=0.30, yes_price=0.50)
    # no model probability → excluded honestly
    await _add_market(db_session, "no-model", volume=9000, model_p=None, yes_price=0.50)
    # model but no market price → excluded (no edge to rank)
    await _add_market(db_session, "no-price", volume=7000, model_p=0.70, yes_price=None)
    # a top signal on big-edge
    db_session.add(
        SignalEvent(
            signal_type="news:mispricing",
            platform="seed",
            market_id="big-edge",
            payload={
                "id": "sig-1",
                "news_url": "https://example.com/n1",
                "headline": "Star player questionable",
                "model_p": 0.80,
                "market_p": 0.50,
            },
            headline_eligible=True,
            created_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_ranking_highest_edge_first(db_session):
    await _seed(db_session)
    r = await _get("/api/v1/opportunities")
    assert r.status_code == 200
    body = r.json()
    rows = body["opportunities"]
    slugs = [row["slug"] for row in rows]
    # low-liq (0.40) > big-edge (0.30) > no-lean (0.20) > small-edge (0.05).
    # no-model and no-price are excluded.
    assert slugs == ["low-liq", "big-edge", "no-lean", "small-edge"]
    assert rows[0]["edge"] == 0.40
    assert rows[0]["direction"] == "YES"
    assert rows[0]["model_p"] == 0.90
    assert rows[0]["market_p"] == 0.50
    assert rows[0]["liquidity"] == 100
    assert body["paper_trading_only"] is True
    assert body["cached"] is False


@pytest.mark.asyncio
async def test_no_model_and_no_price_excluded(db_session):
    await _seed(db_session)
    r = await _get("/api/v1/opportunities")
    slugs = [row["slug"] for row in r.json()["opportunities"]]
    assert "no-model" not in slugs
    assert "no-price" not in slugs


@pytest.mark.asyncio
async def test_liquidity_floor_filters(db_session):
    await _seed(db_session)
    r = await _get("/api/v1/opportunities?min_liquidity=1000")
    rows = r.json()["opportunities"]
    slugs = [row["slug"] for row in rows]
    assert "low-liq" not in slugs  # volume 100 < 1000
    assert slugs == ["big-edge", "no-lean", "small-edge"]


@pytest.mark.asyncio
async def test_direction_filter(db_session):
    await _seed(db_session)
    r = await _get("/api/v1/opportunities?direction=NO")
    rows = r.json()["opportunities"]
    assert [row["slug"] for row in rows] == ["no-lean"]
    assert rows[0]["direction"] == "NO"
    assert r.json()["direction"] == "NO"


@pytest.mark.asyncio
async def test_top_signal_present(db_session):
    await _seed(db_session)
    r = await _get("/api/v1/opportunities")
    big = next(row for row in r.json()["opportunities"] if row["slug"] == "big-edge")
    assert big["top_signal"]["family"] == "news:mispricing"
    assert big["top_signal"]["citation"]["news_url"] == "https://example.com/n1"
    # a market with no signal reports honest null
    small = next(row for row in r.json()["opportunities"] if row["slug"] == "small-edge")
    assert small["top_signal"] is None


@pytest.mark.asyncio
async def test_limit_bounds_rows(db_session):
    await _seed(db_session)
    r = await _get("/api/v1/opportunities?limit=2")
    rows = r.json()["opportunities"]
    assert len(rows) == 2
    assert [row["slug"] for row in rows] == ["low-liq", "big-edge"]


@pytest.mark.asyncio
async def test_honest_empty(db_session):
    r = await _get("/api/v1/opportunities")
    assert r.status_code == 200
    body = r.json()
    assert body["opportunities"] == []
    assert body["count"] == 0


# DIAGNOSIS106-OPPS: the honest empty must be EXPLAINABLE — stable
# empty_reason + real funnel counts, never fabricated rows.


@pytest.mark.asyncio
async def test_honest_empty_includes_empty_reason_no_model(db_session):
    # No markets / no PredictionLog seeded at all: the empty names itself and
    # proves no model probability was invented to fill the list.
    r = await _get("/api/v1/opportunities")
    assert r.status_code == 200
    body = r.json()
    assert body["opportunities"] == []
    assert body["count"] == 0
    # With nothing seeded the funnel stops at the open-candidate gate; the
    # contract allows either reason depending on the seed.
    assert body["empty_reason"] in {"no_model_predictions", "no_open_candidates"}
    assert body["funnel"]["with_model_p"] == 0


@pytest.mark.asyncio
async def test_funnel_counts_with_seeded_edges(db_session):
    await _seed(db_session)
    r = await _get("/api/v1/opportunities")
    assert r.status_code == 200
    body = r.json()
    # Non-empty → no empty reason.
    assert body["empty_reason"] is None
    funnel = body["funnel"]
    # big-edge, small-edge, low-liq, no-lean, no-price carry a PredictionLog
    # (no-model does not).
    assert funnel["with_model_p"] >= 4
    assert funnel["returned"] == body["count"]
    # Ranking unchanged from test_ranking_highest_edge_first.
    slugs = [row["slug"] for row in body["opportunities"]]
    assert slugs == ["low-liq", "big-edge", "no-lean", "small-edge"]


@pytest.mark.asyncio
async def test_empty_reason_filtered_by_min_liquidity(db_session):
    # One open market WITH model + price but tiny volume: the empty is the
    # liquidity floor, and the funnel proves the row existed before the floor.
    await _add_market(db_session, "liq-only", volume=100, model_p=0.90, yes_price=0.50)
    r = await _get("/api/v1/opportunities?min_liquidity=1000")
    assert r.status_code == 200
    body = r.json()
    assert body["opportunities"] == []
    assert body["empty_reason"] == "filtered_by_min_liquidity"
    assert body["funnel"]["with_model_p"] == 1
    assert body["funnel"]["after_min_liquidity"] == 0


@pytest.mark.asyncio
async def test_empty_reason_filtered_by_direction(db_session):
    # Only YES-lean edges seeded → asking for NO leans empties the list.
    await _add_market(db_session, "yes-lean", volume=5000, model_p=0.80, yes_price=0.50)
    r = await _get("/api/v1/opportunities?direction=NO")
    assert r.status_code == 200
    body = r.json()
    assert body["opportunities"] == []
    assert body["empty_reason"] == "filtered_by_direction"


@pytest.mark.asyncio
async def test_empty_reason_no_open_candidates(db_session):
    # Only RESOLVED markets (which DO carry a PredictionLog): resolved markets
    # have a known outcome — no live edge — so the candidate set is empty.
    now = datetime.now(UTC)
    db_session.add(
        Market(
            slug="resolved-1",
            title="Market resolved-1",
            question="?",
            status=MarketStatus.RESOLVED,
            volume=5000,
        )
    )
    await db_session.flush()
    db_session.add(
        PredictionLog(
            market_slug="resolved-1",
            predicted_prob=Decimal("0.80"),
            confidence=Decimal("0.7"),
            predicted_at=now - timedelta(hours=1),
        )
    )
    await db_session.flush()
    r = await _get("/api/v1/opportunities")
    assert r.status_code == 200
    body = r.json()
    assert body["opportunities"] == []
    assert body["empty_reason"] == "no_open_candidates"
    assert body["funnel"]["candidates_open"] == 0


@pytest.mark.asyncio
async def test_top_signal_resolved_only_for_returned_rows(db_session, monkeypatch):
    """Perf regression guard (V12 Q02): the per-slug top_signal lookup runs once
    per RETURNED row, never once per scored candidate. Four markets survive
    scoring; at limit=2 exactly two lookups happen (was four pre-deferral)."""
    import app.api.v1.opportunities as opp_mod

    await _seed(db_session)
    calls: list[str] = []
    original = opp_mod._top_signal

    async def _counting(db, slug):
        calls.append(slug)
        return await original(db, slug)

    monkeypatch.setattr(opp_mod, "_top_signal", _counting)
    r = await _get("/api/v1/opportunities?limit=2")
    assert r.status_code == 200
    rows = r.json()["opportunities"]
    assert len(rows) == 2
    assert calls == [row["slug"] for row in rows]
    assert len(calls) == 2
