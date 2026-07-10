"""I01 — Public-GET 5xx guard (Loop V4).

Standing guard against the calibration-class regression: a public GET that is
green on happy-path fixtures but 500s on a REAL prod data shape. The prod bug
this encodes: ``/api/v1/calibration/latest`` crashed only when a RESOLVED
market (with ``winning_outcome``) had a paper order AND a populated
``resolved_at`` — a shape no fixture seeded. This module seeds exactly those
edge shapes once, then sweeps EVERY public GET route in ``app.openapi()`` and
asserts none of them returns a 5xx.

Seeded edge shapes:
* a RESOLVED market with ``winning_outcome`` + a settled paper order + a
  populated ``resolved_at`` (the calibration/track-record fallback path);
* an OPEN market with NO candles / book / predictions (empty-detail paths);
* every other table left empty (honest-empty paths everywhere else).

Skipped honestly: routes whose OpenAPI op declares a security requirement,
admin-prefixed paths (need admin headers), and routes with path params other
than ``{slug}`` that cannot be satisfied from the seeded data. ``{slug}``
path params are swept once per seeded slug. Request-time network connectors
(macro/FRED, weather/NWS) are stubbed to their honest-empty results so the
sweep stays offline — the route handlers themselves still execute.

If someone reintroduces the calibration-class bug, this module FAILS.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import Market, MarketStatus, OrderOutcome, PaperOrder, User
from app.db.session import get_db
from app.main import app

RESOLVED_SLUG = "guard-resolved-lal-bos"
NO_CANDLES_SLUG = "guard-open-no-candles"

# Routes the sweep must always cover — a refactor that silently drops these
# from the sweep (renamed path, accidental security marker) must fail loudly,
# because they are the exact endpoints the prod 500 hit.
MUST_COVER = (
    "/api/v1/calibration/latest",
    "/api/v1/track-record",
    "/api/v1/backtest/summary",
    "/api/v1/alerts/feed",
    "/api/v1/alerts/digest",
    "/api/v1/home",
    "/api/v1/opportunities",
)

# Public GETs that authenticate *optionally* (get_optional_user) carry an
# HTTPBearer marker in the OpenAPI op even though they serve anonymous callers.
# The generic sweep skips anything with a security marker, so these must be
# force-included: they are genuinely public and must survive edge-case data.
OPTIONAL_AUTH_PUBLIC_GETS = (
    "/api/v1/alerts/feed",
    "/api/v1/home",
)


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Keep the sweep offline: stub request-time upstream connectors to their
    honest-empty results (exactly what they return on upstream failure)."""
    from app.data.connectors.fred import FredConnector
    from app.services.weather_desk import WeatherDeskService

    monkeypatch.setattr(FredConnector, "fetch_indicators", lambda self: [])
    monkeypatch.setattr(WeatherDeskService, "scan", lambda self, day: [])


async def _seed_edge_case_data(db_session) -> None:
    user = User(email="guard-5xx@example.com", hashed_password="hash")
    resolved = Market(
        slug=RESOLVED_SLUG,
        title="Guard: resolved market with paper order",
        question="Did the resolved+paper-order+resolved_at shape stay 200?",
        status=MarketStatus.RESOLVED,
        winning_outcome=OrderOutcome.YES,
        resolved_at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    no_candles = Market(
        slug=NO_CANDLES_SLUG,
        title="Guard: open market with no candles",
        question="Does an open market with zero candles stay 200?",
        status=MarketStatus.OPEN,
    )
    db_session.add_all([user, resolved, no_candles])
    await db_session.flush()
    db_session.add(
        PaperOrder(
            user_id=user.id,
            slug=resolved.slug,
            side="YES",
            outcome="yes",
            shares=Decimal("10"),
            price=Decimal("0.60"),
            cost=Decimal("6.00"),
            settled=True,
            realized_pnl=Decimal("4.00"),
        )
    )
    await db_session.flush()


def _collect_public_get_urls() -> tuple[list[str], list[str]]:
    """(urls to sweep, skipped paths) from the live OpenAPI schema."""
    schema = app.openapi()
    urls: list[str] = []
    skipped: list[str] = []
    for path, ops in schema.get("paths", {}).items():
        op = ops.get("get")
        if op is None:
            continue
        if op.get("security") and path not in OPTIONAL_AUTH_PUBLIC_GETS:
            skipped.append(f"{path} (auth required)")
            continue
        if "/admin" in path:
            skipped.append(f"{path} (admin headers required)")
            continue
        path_params = [
            p["name"]
            for p in op.get("parameters", [])
            if p.get("in") == "path"
        ]
        if any(name != "slug" for name in path_params):
            skipped.append(f"{path} (unsatisfiable path params: {path_params})")
            continue

        if "{slug}" in path:
            candidates = [
                path.replace("{slug}", RESOLVED_SLUG),
                path.replace("{slug}", NO_CANDLES_SLUG),
            ]
        else:
            candidates = [path]

        # Fill any REQUIRED slug query param from the seeded markets so the
        # handler actually runs (422 short-circuits would hide 500s there).
        required_slug_query = any(
            p.get("in") == "query"
            and p.get("required")
            and p["name"] == "slug"
            for p in op.get("parameters", [])
        )
        if required_slug_query:
            candidates = [
                f"{candidate}?slug={seeded}"
                for candidate in [path]
                for seeded in (RESOLVED_SLUG, NO_CANDLES_SLUG)
            ]

        urls.extend(candidates)
    return urls, skipped


@pytest.mark.asyncio
async def test_every_public_get_survives_edge_case_data(db_session):
    await _seed_edge_case_data(db_session)
    urls, _skipped = _collect_public_get_urls()

    for must in MUST_COVER:
        assert must in urls, (
            f"5xx sweep no longer covers {must} — the guard has been weakened"
        )

    failures: list[str] = []
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for url in urls:
            response = await client.get(url)
            if response.status_code >= 500:
                failures.append(f"{url} -> {response.status_code}")

    assert not failures, (
        "Public GET routes returned 5xx on edge-case data "
        f"(calibration-class regression): {failures}"
    )
    # Sanity: the sweep exercised a meaningful surface, not an empty schema.
    assert len(urls) >= 20, f"suspiciously small sweep: {len(urls)} routes"


@pytest.mark.asyncio
async def test_calibration_route_uses_seeded_paper_order_path(db_session):
    """The seeded shape must actually flow through the paper-orders fallback
    (the code path behind the prod 500) — not just return no-data."""
    await _seed_edge_case_data(db_session)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/calibration/latest")
    assert response.status_code == 200
    body = response.json()
    assert body["markets_evaluated"] == 1
    assert body["gate"] != "no-data"
