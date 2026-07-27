"""loop116 — the fired-alert dashboard artifact (VIDEO-PARITY-AUDIT gap #2).

Covers the four behaviours the artifact has to get right:

1. A fired run assembles a complete document (headline, fired pill, KPI tiles,
   step counters, matched-markets table, chart series, narrative).
2. An empty run assembles one too, and says so HONESTLY — fired is False, the
   match table is empty, and the chart carries an explicit empty reason.
3. PAPER LAW: an LLM narrative containing "buy YES now" is filtered out; nothing
   with trade / stake / side language ever reaches the artifact.
4. The artifact endpoint's visibility mirrors the scanner's exactly — public is
   public, private is owner-only, and a miss is a 404 (never a 403).

Plus the standing order-path guard: this service must not import RiskService or
OrderBookService.
"""

from __future__ import annotations

import ast
import pathlib
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import Scanner, ScannerRun
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService
from app.services.scanner_artifact_service import (
    GENERATOR_DETERMINISTIC,
    assemble_run_artifact,
    contains_trade_language,
    filter_action_items,
    filter_trade_language,
)

SPEC = {
    "name": "Aligned edge radar",
    "universe": {"categories": ["sports"], "minimum_volume": 100},
    "schedule": {"timezone": "UTC", "market_hours_only": False, "interval_minutes": 30},
    "steps": [
        {"type": "WHALE_FLOW"},
        {"type": "PRICE_TREND", "window_days": 7},
        {"type": "MODEL_EDGE"},
    ],
    "delivery": {"email": False, "in_app": True, "cooldown_minutes": 120},
    "limit": 10,
}


async def _client_for(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_market(db_session, slug: str, *, volume: int = 42000):
    return await MarketService(db_session).create_market(
        slug=slug,
        title=f"Title for {slug}",
        question="Will the artifact assemble?",
        lock_at=datetime.now(UTC) + timedelta(hours=6),
        category="Sports",
        volume=volume,
    )


def _candidate(slug: str, *, aligned: bool, edge: float = 0.08) -> dict:
    return {
        "market_slug": slug,
        "title": f"Title for {slug}",
        "aligned": aligned,
        "reads": {
            "WHALE_FLOW": {
                "direction": "up",
                "pressure": 0.42,
                "event_count": 7,
                "net_notional": 12000.0,
                "total_notional": 30000.0,
            },
            "PRICE_TREND": {"direction": "up", "change": 0.031, "window_days": 7},
            "MODEL_EDGE": {
                "direction": "up",
                "edge": edge,
                "model_prob": 0.61,
                "market_prob": 0.61 - edge,
            },
        },
    }


async def _scanner_with_run(
    db_session,
    *,
    status: str,
    candidates: list[dict],
    aligned_n: int,
    universe: int,
    is_public: bool = True,
    owner: str | None = None,
) -> tuple[Scanner, ScannerRun]:
    scanner = Scanner(
        name="Aligned edge radar",
        description="loop116 fixture",
        owner=owner,
        spec=SPEC,
        status="active",
        is_public=is_public,
    )
    db_session.add(scanner)
    await db_session.flush()

    started = datetime.now(UTC) - timedelta(seconds=9)
    run = ScannerRun(
        scanner_id=scanner.id,
        status=status,
        started_at=started,
        finished_at=started + timedelta(seconds=4),
        checkpoint={"node": 2},
        result={
            "candidates": candidates,
            "top_pick": next((c for c in candidates if c.get("aligned")), None),
            "counts": {
                "universe": universe,
                "candidates": len(candidates),
                "aligned": aligned_n,
            },
            "step_counters": [
                {"index": 0, "step": "WHALE_FLOW", "type": "WHALE_FLOW", "in": universe, "out": universe},
                {
                    "index": 1,
                    "step": "PRICE_TREND",
                    "type": "PRICE_TREND",
                    "in": universe,
                    "out": max(len(candidates), 0),
                },
                {
                    "index": 2,
                    "step": "MODEL_EDGE",
                    "type": "MODEL_EDGE",
                    "in": max(len(candidates), 0),
                    "out": max(len(candidates), 0),
                },
            ],
        },
    )
    db_session.add(run)
    await db_session.flush()
    return scanner, run


# ---------------------------------------------------------------------------
# 1. fired run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_artifact_assembled_for_fired_run(db_session):
    await _seed_market(db_session, "loop116-fired-a", volume=51000)
    await _seed_market(db_session, "loop116-fired-b", volume=22000)
    candidates = [
        _candidate("loop116-fired-a", aligned=True, edge=0.09),
        _candidate("loop116-fired-b", aligned=True, edge=0.03),
        _candidate("loop116-fired-c", aligned=False, edge=0.01),
    ]
    scanner, run = await _scanner_with_run(
        db_session, status="completed", candidates=candidates, aligned_n=2, universe=40
    )

    artifact = await assemble_run_artifact(db_session, scanner, run, use_llm=False)

    assert artifact["fired"] is True
    assert "2 aligned markets" in artifact["headline"]
    assert artifact["run_meta"]["scanner_name"] == "Aligned edge radar"
    assert artifact["run_meta"]["interval_minutes"] == 30
    assert artifact["run_meta"]["duration_ms"] == 4000
    assert artifact["run_meta"]["paper_trading_only"] is True

    kpi = {k["label"]: k["value"] for k in artifact["kpis"]}
    assert kpi["Matches"] == 2
    assert kpi["Universe scanned"] == 40
    assert kpi["Top match"] == "Title for loop116-fired-a"
    assert kpi["Soonest lock"] != "—"

    assert [c["step"] for c in artifact["step_counters"]] == [
        "WHALE_FLOW",
        "PRICE_TREND",
        "MODEL_EDGE",
    ]
    assert all(c["measured"] for c in artifact["step_counters"])

    # Matched-markets table: only aligned rows, ranked by signal strength,
    # carrying per-step score fields plus market facts off the markets table.
    assert [m["market_slug"] for m in artifact["matches"]] == [
        "loop116-fired-a",
        "loop116-fired-b",
    ]
    top = artifact["matches"][0]
    assert top["volume"] == 51000
    assert top["lock_at"] is not None
    assert top["price"] == pytest.approx(0.52)
    assert set(top["scores"]) == {"WHALE_FLOW", "PRICE_TREND", "MODEL_EDGE"}
    assert top["score"] > artifact["matches"][1]["score"]

    assert artifact["chart"]["type"] == "bar"
    assert len(artifact["chart"]["series"]) == 2
    assert artifact["chart"]["empty_reason"] is None

    narrative = artifact["narrative"]
    assert narrative["generator"] == GENERATOR_DETERMINISTIC
    assert "cleared every step" in narrative["what_this_means"]
    assert len(narrative["what_to_do_now"]) >= 2
    for action in narrative["what_to_do_now"]:
        assert not contains_trade_language(action)


# ---------------------------------------------------------------------------
# 2. empty run — honest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_artifact_assembled_honestly_for_empty_run(db_session):
    scanner, run = await _scanner_with_run(
        db_session, status="empty", candidates=[], aligned_n=0, universe=37
    )

    artifact = await assemble_run_artifact(db_session, scanner, run, use_llm=False)

    assert artifact["fired"] is False
    assert "cleared no markets" in artifact["headline"]
    assert artifact["matches"] == []
    assert artifact["chart"]["series"] == []
    assert artifact["chart"]["empty_reason"] == "No market cleared every step."

    kpi = {k["label"]: k["value"] for k in artifact["kpis"]}
    assert kpi["Matches"] == 0
    assert kpi["Top match"] == "—"
    assert kpi["Soonest lock"] == "—"
    assert kpi["Universe scanned"] == 37

    what = artifact["narrative"]["what_this_means"]
    # Honest: names it as an empty result, not an error, and does not pretend
    # anything was found.
    assert "No market cleared all 3 steps" in what
    assert "not a failure" in what
    assert artifact["narrative"]["what_to_do_now"]
    for action in artifact["narrative"]["what_to_do_now"]:
        assert not contains_trade_language(action)


@pytest.mark.asyncio
async def test_artifact_reports_empty_universe_distinctly(db_session):
    scanner, run = await _scanner_with_run(
        db_session, status="empty", candidates=[], aligned_n=0, universe=0
    )
    artifact = await assemble_run_artifact(db_session, scanner, run, use_llm=False)
    assert artifact["chart"]["empty_reason"] == "No open markets in the universe."
    assert "no open markets to scan" in artifact["headline"]


# ---------------------------------------------------------------------------
# 3. PAPER LAW — narrative filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_narrative_filter_strips_trade_language(db_session, monkeypatch):
    await _seed_market(db_session, "loop116-filter-a")
    scanner, run = await _scanner_with_run(
        db_session,
        status="completed",
        candidates=[_candidate("loop116-filter-a", aligned=True)],
        aligned_n=1,
        universe=12,
    )

    async def _mock_llm(payload, settings):
        return {
            "what_this_means": (
                "One market cleared every step in this scan. "
                "You should buy YES now before the price moves."
            ),
            "what_to_do_now": [
                "Read the analyst brief for the matched market.",
                "Buy YES now with a 5% stake.",
                "Compare the matched market against its cross-venue mirror.",
                "Place a trade before the market locks.",
            ],
        }

    monkeypatch.setattr(
        "app.services.scanner_artifact_service._llm_narrative", _mock_llm
    )

    artifact = await assemble_run_artifact(
        db_session, scanner, run, settings=object(), use_llm=True
    )
    narrative = artifact["narrative"]

    assert narrative["filtered"] is True
    assert narrative["generator"] == "llm-filtered"

    # The clean sentence survives; the trade instruction does not.
    assert "cleared every step" in narrative["what_this_means"]
    assert "buy YES now" not in narrative["what_this_means"].lower()
    assert not contains_trade_language(narrative["what_this_means"])

    assert narrative["what_to_do_now"] == [
        "Read the analyst brief for the matched market.",
        "Compare the matched market against its cross-venue mirror.",
    ]
    for action in narrative["what_to_do_now"]:
        assert not contains_trade_language(action)


@pytest.mark.asyncio
async def test_fully_stripped_llm_narrative_falls_back_to_template(db_session, monkeypatch):
    await _seed_market(db_session, "loop116-filter-b")
    scanner, run = await _scanner_with_run(
        db_session,
        status="completed",
        candidates=[_candidate("loop116-filter-b", aligned=True)],
        aligned_n=1,
        universe=9,
    )

    async def _all_trade_talk(payload, settings):
        return {
            "what_this_means": "Buy YES now and size up your position.",
            "what_to_do_now": ["Sell the NO side.", "Stake 10% of your bankroll."],
        }

    monkeypatch.setattr(
        "app.services.scanner_artifact_service._llm_narrative", _all_trade_talk
    )

    artifact = await assemble_run_artifact(
        db_session, scanner, run, settings=object(), use_llm=True
    )
    narrative = artifact["narrative"]
    assert narrative["generator"] == GENERATOR_DETERMINISTIC
    assert narrative["filtered"] is True
    assert not contains_trade_language(narrative["what_this_means"])
    assert all(not contains_trade_language(a) for a in narrative["what_to_do_now"])


@pytest.mark.asyncio
async def test_llm_failure_never_breaks_the_artifact(db_session, monkeypatch):
    scanner, run = await _scanner_with_run(
        db_session, status="empty", candidates=[], aligned_n=0, universe=5
    )

    async def _boom(payload, settings):
        raise RuntimeError("provider 503")

    monkeypatch.setattr("app.services.scanner_artifact_service._llm_narrative", _boom)

    artifact = await assemble_run_artifact(
        db_session, scanner, run, settings=object(), use_llm=True
    )
    assert artifact["narrative"]["generator"] == GENERATOR_DETERMINISTIC
    assert artifact["headline"]


@pytest.mark.parametrize(
    "text",
    [
        "Buy YES now.",
        "Consider selling before the lock.",
        "Stake 2% of the bankroll.",
        "Place a trade on the favourite.",
        "Set a stop-loss at 0.40.",
        "Take the YES side here.",
        "Go long this contract.",
    ],
)
def test_trade_language_detector_catches_instructions(text):
    assert contains_trade_language(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "Watch the market that locks soonest.",
        "Compare the matched markets side by side.",
        "Read the analyst brief for the top match.",
        "Re-run the scan later to see whether the same markets clear again.",
        "Better coverage would need a wider universe.",
        "Sellers and buyers are not named here, so this sentence must survive.",
    ],
)
def test_trade_language_detector_leaves_research_prose_alone(text):
    assert contains_trade_language(text) is False
    assert filter_trade_language(text) == text.strip()


def test_filter_action_items_drops_only_offending_bullets():
    kept = filter_action_items(
        [
            "- Read the brief.",
            "Buy YES now.",
            "  ",
            "Compare the two mirrors.",
        ]
    )
    assert kept == ["Read the brief.", "Compare the two mirrors."]


# ---------------------------------------------------------------------------
# 4. endpoint auth mirrors scanner visibility
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_artifact_endpoint_auth_mirrors_scanner_visibility(db_session):
    await _seed_market(db_session, "loop116-auth-a")
    public_scanner, public_run = await _scanner_with_run(
        db_session,
        status="completed",
        candidates=[_candidate("loop116-auth-a", aligned=True)],
        aligned_n=1,
        universe=11,
        is_public=True,
        owner="owner-placeholder",
    )

    client = await _client_for(db_session)
    async with client:
        # Anonymous can read a PUBLIC scanner's artifact.
        anon = await client.get(
            f"/api/v1/scanners/{public_scanner.id}/runs/{public_run.id}/artifact"
        )
        assert anon.status_code == 200, anon.text
        body = anon.json()
        assert body["fired"] is True
        assert body["source"] == "on-read"  # not stamped by the executor here
        assert body["run_meta"]["run_id"] == str(public_run.id)
        assert not contains_trade_language(body["narrative"]["what_this_means"])

        # Two distinct users: the owner and a stranger.
        owner_signup = await client.post(
            "/api/v1/auth/signup",
            json={"email": "loop116-owner@example.com", "password": "correct-horse-battery-staple"},
        )
        assert owner_signup.status_code == 201, owner_signup.text
        owner_headers = {"Authorization": f"Bearer {owner_signup.json()['access_token']}"}

        stranger_signup = await client.post(
            "/api/v1/auth/signup",
            json={"email": "loop116-stranger@example.com", "password": "correct-horse-battery-staple"},
        )
        assert stranger_signup.status_code == 201, stranger_signup.text
        stranger_headers = {
            "Authorization": f"Bearer {stranger_signup.json()['access_token']}"
        }

        me = await client.get("/api/v1/auth/me", headers=owner_headers)
        assert me.status_code == 200, me.text
        owner_id = str(me.json()["id"])

        private_scanner, private_run = await _scanner_with_run(
            db_session,
            status="empty",
            candidates=[],
            aligned_n=0,
            universe=4,
            is_public=False,
            owner=owner_id,
        )
        url = f"/api/v1/scanners/{private_scanner.id}/runs/{private_run.id}/artifact"

        # Owner: 200. Anonymous + stranger: 404 (never 403 — no existence leak).
        assert (await client.get(url, headers=owner_headers)).status_code == 200
        assert (await client.get(url)).status_code == 404
        assert (await client.get(url, headers=stranger_headers)).status_code == 404

        # A run id that belongs to another scanner is a 404, not a cross-read.
        crossed = await client.get(
            f"/api/v1/scanners/{public_scanner.id}/runs/{private_run.id}/artifact"
        )
        assert crossed.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_stored_artifact_is_served_verbatim(db_session):
    scanner, run = await _scanner_with_run(
        db_session, status="empty", candidates=[], aligned_n=0, universe=3
    )
    stored = await assemble_run_artifact(db_session, scanner, run, use_llm=False)
    run.artifact = stored
    await db_session.flush()

    client = await _client_for(db_session)
    async with client:
        resp = await client.get(
            f"/api/v1/scanners/{scanner.id}/runs/{run.id}/artifact"
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["source"] == "stored"
        assert body["generated_at"] == stored["generated_at"]
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Executor wiring — a real run stamps its own artifact
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_stamps_artifact_and_measured_step_counters(
    db_session, monkeypatch
):
    """End-to-end: run_scanner() persists run.artifact with a MEASURED funnel."""
    from app.services.scanner_executor_service import run_scanner

    async def _no_network_news(topic: str, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.scanner_executor_service.fetch_news_signal", _no_network_news
    )

    for slug in ("loop116-exec-a", "loop116-exec-b"):
        await _seed_market(db_session, slug, volume=33000)

    scanner = Scanner(
        name="Executor wiring probe",
        spec=SPEC,
        status="active",
        is_public=True,
        owner=None,
    )
    db_session.add(scanner)
    await db_session.flush()

    run = await run_scanner(db_session, scanner)

    assert run.status in {"completed", "empty"}
    assert isinstance(run.artifact, dict), "executor must stamp the artifact"
    assert run.artifact["run_meta"]["run_id"] == str(run.id)
    assert run.artifact["headline"]
    # The funnel is measured by the executor, never inferred.
    counters = run.artifact["step_counters"]
    assert [c["step"] for c in counters] == ["WHALE_FLOW", "PRICE_TREND", "MODEL_EDGE"]
    assert all(c["measured"] for c in counters)
    assert counters[0]["in"] == run.result["counts"]["universe"]
    assert run.result["step_counters"] == [
        {k: c[k] for k in ("index", "step", "type", "in", "out")} for c in counters
    ]
    # Paper law holds on the deterministic path too.
    assert not contains_trade_language(run.artifact["narrative"]["what_this_means"])
    for action in run.artifact["narrative"]["what_to_do_now"]:
        assert not contains_trade_language(action)


@pytest.mark.asyncio
async def test_executor_stamps_an_honest_artifact_on_an_empty_universe(
    db_session, monkeypatch
):
    """No open market matches the universe filter -> empty run, honest artifact."""
    from app.services.scanner_executor_service import run_scanner

    async def _no_network_news(topic: str, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.scanner_executor_service.fetch_news_signal", _no_network_news
    )

    scanner = Scanner(
        name="Empty universe probe",
        spec={**SPEC, "universe": {"categories": ["no-such-category"], "minimum_volume": 0}},
        status="active",
        is_public=True,
        owner=None,
    )
    db_session.add(scanner)
    await db_session.flush()

    run = await run_scanner(db_session, scanner)

    assert run.status == "empty"
    assert isinstance(run.artifact, dict)
    assert run.artifact["fired"] is False
    assert run.artifact["matches"] == []
    assert run.artifact["chart"]["empty_reason"] == "No open markets in the universe."
    assert "no open markets to scan" in run.artifact["headline"]


# ---------------------------------------------------------------------------
# Standing guardrail
# ---------------------------------------------------------------------------


def test_artifact_service_never_imports_the_order_path():
    """§G2: the artifact layer must not reach RiskService / OrderBookService."""
    src = (
        pathlib.Path(__file__).parent.parent
        / "app"
        / "services"
        / "scanner_artifact_service.py"
    )
    tree = ast.parse(src.read_text(encoding="utf-8"))
    banned = {"OrderBookService", "RiskService", "OrderIntent", "app.risk.rules"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name or "" for alias in node.names]
            if isinstance(node, ast.ImportFrom):
                names.append(node.module or "")
            for name in names:
                assert name not in banned, (
                    f"scanner_artifact_service.py must not import {name} "
                    "(§G2 order-path guardrail)"
                )
