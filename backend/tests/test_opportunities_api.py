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
    AlphaRun,
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


async def _seed_validator_verdict(db_session, *, valid: bool, t_stat: float) -> None:
    """Persist an alpha validator report exactly as ``AlphaRunService`` writes it.

    Loop107: the opportunity board reads this verdict — it never recomputes the
    statistics. Tests that exercise ranking/filtering seed the VALID branch so
    the ranking contract stays covered; the gate tests seed the rejecting branch
    (or nothing at all) that production actually reports today.
    """
    db_session.add(
        AlphaRun(
            run_date=datetime.now(UTC).date(),
            status="genuine_edge" if valid else "no_signal",
            result={
                "validations": [
                    {
                        "name": "model_edge",
                        "valid": valid,
                        "t_stat": t_stat,
                        "reason": None if valid else "insufficient_oos_edge",
                    }
                ]
            },
            rejection_reasons=[],
        )
    )
    await db_session.flush()


async def _seed(db_session) -> None:
    # The ranking/filter contract below is about ordering, not about whether the
    # family is validated — so seed the validator's PASS branch explicitly.
    await _seed_validator_verdict(db_session, valid=True, t_stat=3.4)
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
    await _seed_validator_verdict(db_session, valid=True, t_stat=3.4)
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
    await _seed_validator_verdict(db_session, valid=True, t_stat=3.4)
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


# Loop107 CLV gate: an edge is NEVER presented as validated until the alpha
# validator's report says the factor family beat the closing line out-of-sample.
# The board being empty is the correct outcome, not a bug to work around.


@pytest.mark.asyncio
async def test_signal_only_true_blocks_unvalidated_edges_even_with_predictions(
    db_session,
):
    # Production's actual state: the validator REJECTS model_edge (t=-3.19).
    await _seed_validator_verdict(db_session, valid=False, t_stat=-3.19)
    await _add_market(db_session, "big-edge", volume=5000, model_p=0.80, yes_price=0.50)
    await _add_market(db_session, "no-lean", volume=3000, model_p=0.30, yes_price=0.50)

    r = await _get("/api/v1/opportunities")
    assert r.status_code == 200
    body = r.json()
    # Model probabilities EXIST — the writer did its job — and the board is
    # still empty because the edge is not validated.
    assert body["funnel"]["with_model_p"] == 2
    assert body["funnel"]["with_market_p"] == 2
    assert body["opportunities"] == []
    assert body["count"] == 0
    assert body["signal_only"] is True
    assert body["validated"] is False
    assert body["validated_factor_family"] == "model_edge"


@pytest.mark.asyncio
async def test_after_signal_gate_counter_and_no_validated_edge_reason(db_session):
    await _seed_validator_verdict(db_session, valid=False, t_stat=-3.19)
    await _add_market(db_session, "big-edge", volume=5000, model_p=0.80, yes_price=0.50)

    r = await _get("/api/v1/opportunities")
    body = r.json()
    funnel = body["funnel"]
    assert funnel["with_model_p"] > 0
    assert funnel["after_signal_gate"] == 0
    assert funnel["returned"] == 0
    assert body["empty_reason"] == "no_validated_edge"

    # With NO validator report at all the gate stays shut: absence of evidence
    # is not evidence of an edge.
    opportunities_cache.invalidate()
    await _add_market(db_session, "other", volume=4000, model_p=0.20, yes_price=0.50)
    r2 = await _get("/api/v1/opportunities")
    assert r2.json()["empty_reason"] == "no_validated_edge"
    assert r2.json()["funnel"]["after_signal_gate"] == 0


@pytest.mark.asyncio
async def test_signal_only_false_rows_carry_validated_false_marker(db_session):
    await _seed_validator_verdict(db_session, valid=False, t_stat=-3.19)
    await _add_market(db_session, "big-edge", volume=5000, model_p=0.80, yes_price=0.50)
    await _add_market(db_session, "no-lean", volume=3000, model_p=0.30, yes_price=0.50)

    r = await _get("/api/v1/opportunities?signal_only=false")
    assert r.status_code == 200
    body = r.json()
    rows = body["opportunities"]
    # Raw gaps are visible for inspection ONLY because they are labelled.
    assert [row["slug"] for row in rows] == ["big-edge", "no-lean"]
    assert body["signal_only"] is False
    assert body["validated"] is False
    assert all(row["validated"] is False for row in rows)
    assert body["funnel"]["after_signal_gate"] == 2
