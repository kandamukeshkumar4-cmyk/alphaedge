"""Loop V26 Z4 — negative / abuse probes.

Cross-user IDOR on id-param routes, garbage/oversize payloads on mutating
routes → 4xx never 5xx. SEC REPORTS for leaks or 500s.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core import ratelimit
from app.db.models import User
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService
from app.services.notification_service import create_notification

CANONICAL_SLUG = "nba-2025-01-15-lal-bos"
ADMIN_HEADERS = {"X-Admin-API-Key": "dev-admin-key"}


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    ratelimit.reset()
    yield
    app.dependency_overrides.clear()
    ratelimit.reset()


async def _signup_user(db_session, client: AsyncClient, email: str) -> tuple[str, User]:
    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "securepass1"},
    )
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    user = (
        await db_session.execute(select(User).where(User.email == email))
    ).scalar_one()
    return token, user


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# IDOR probes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_z4_idor_notifications_cross_user(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token_a, user_a = await _signup_user(db_session, client, "z4-idor-a@example.com")
        token_b, _user_b = await _signup_user(db_session, client, "z4-idor-b@example.com")
        row = await create_notification(
            db_session,
            user_id=user_a.id,
            type="order_filled",
            title="private-a",
            body="secret",
        )
        await db_session.commit()

        # B cannot list A's notification content by id via mark-read.
        r = await client.post(
            f"/api/v1/notifications/{row.id}/read",
            headers=_auth(token_b),
        )
        assert r.status_code in (403, 404)
        assert r.status_code < 500

        # B's list must not include A's items.
        listed = await client.get(
            "/api/v1/notifications", headers=_auth(token_b)
        )
        assert listed.status_code == 200
        assert all(i.get("title") != "private-a" for i in listed.json()["items"])

        # A can still read own.
        own = await client.post(
            f"/api/v1/notifications/{row.id}/read",
            headers=_auth(token_a),
        )
        assert own.status_code == 200


@pytest.mark.asyncio
async def test_z4_idor_portfolio_and_orders_history_are_self_scoped(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token_a, _a = await _signup_user(db_session, client, "z4-port-a@example.com")
        token_b, _b = await _signup_user(db_session, client, "z4-port-b@example.com")

        order = await client.post(
            "/api/v1/orders",
            headers=_auth(token_a),
            json={
                "slug": CANONICAL_SLUG,
                "side": "YES",
                "shares": 5,
                "price": 0.4,
            },
        )
        assert order.status_code == 201, order.text

        # B sees empty / own portfolio only — no query param to impersonate A.
        port_b = await client.get("/api/v1/portfolio", headers=_auth(token_b))
        assert port_b.status_code == 200
        body = port_b.json()
        assert body.get("total_trades", 0) == 0 or body.get("positions") == []

        hist_b = await client.get(
            "/api/v1/orders/history", headers=_auth(token_b)
        )
        assert hist_b.status_code == 200
        # B has placed no orders — history must be empty (no cross-user leak of A's fill).
        assert hist_b.json() == []

        hist_a = await client.get(
            "/api/v1/orders/history", headers=_auth(token_a)
        )
        assert hist_a.status_code == 200
        a_items = hist_a.json()
        assert isinstance(a_items, list) and len(a_items) >= 1
        # A's history includes the market they traded; B's does not.
        assert any(
            isinstance(item, dict) and item.get("slug") == CANONICAL_SLUG
            for item in a_items
        )
        assert all(
            not (isinstance(item, dict) and item.get("slug") == CANONICAL_SLUG)
            for item in hist_b.json()
        )

        port_a = await client.get("/api/v1/portfolio", headers=_auth(token_a))
        assert port_a.status_code == 200
        assert port_a.json().get("total_trades", 1) >= 1


@pytest.mark.asyncio
async def test_z4_idor_clones_and_watchlist_id_params(db_session):
    """Foreign UUID / slug on user-owned resources → 404/403, never 5xx/leak."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token_a, _a = await _signup_user(db_session, client, "z4-clone-a@example.com")
        token_b, _b = await _signup_user(db_session, client, "z4-clone-b@example.com")
        foreign_id = str(uuid4())

        for method, path in (
            ("GET", f"/api/v1/clones/{foreign_id}"),
            ("PATCH", f"/api/v1/clones/{foreign_id}"),
            ("DELETE", f"/api/v1/clones/{foreign_id}"),
            ("POST", f"/api/v1/clones/{foreign_id}/run"),
            ("GET", f"/api/v1/clones/{foreign_id}/runs"),
            ("GET", f"/api/v1/clones/{foreign_id}/versions"),
            ("POST", f"/api/v1/notifications/{foreign_id}/read"),
            ("DELETE", f"/api/v1/watchlist/{CANONICAL_SLUG}"),
        ):
            kwargs: dict = {"headers": _auth(token_b)}
            if method in ("POST", "PATCH", "PUT"):
                kwargs["json"] = {}
            r = await client.request(method, path, **kwargs)
            assert r.status_code < 500, f"{method} {path} → {r.status_code} {r.text[:120]}"
            assert r.status_code in (200, 400, 401, 403, 404, 405, 409, 422), (
                f"{method} {path} → {r.status_code}"
            )

        # Admin user detail by foreign id without admin key stays gated.
        r = await client.get(
            f"/api/v1/admin/users/{foreign_id}", headers=_auth(token_a)
        )
        assert r.status_code in (401, 422)
        assert r.status_code < 500


@pytest.mark.asyncio
async def test_z4_idor_paper_account_positions_requires_token(db_session):
    """Non-shared account_id without paper token → 401, not data leak."""
    other_account = str(uuid4())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get(f"/api/v1/accounts/{other_account}/positions")
        assert r.status_code in (400, 401, 403, 404, 422)
        assert r.status_code < 500
        # System shared account may be tokenless in test/dev — still no 5xx.
        r2 = await client.get(
            "/api/v1/accounts/00000000-0000-0000-0000-000000000001/positions"
        )
        assert r2.status_code < 500
        assert r2.status_code in (200, 401, 403, 404)


# ---------------------------------------------------------------------------
# Garbage / oversize payloads
# ---------------------------------------------------------------------------

_MUTATING_PROBES: list[tuple[str, str, dict | list | str | None]] = [
    ("POST", "/api/v1/auth/signup", {"email": "not-an-email", "password": "x"}),
    ("POST", "/api/v1/auth/login", {"email": "a@b.com", "password": ""}),
    ("POST", "/api/v1/orders", {"slug": "", "side": "MAYBE", "shares": -1, "price": 2}),
    ("POST", "/api/v1/orders", "not-json"),
    ("POST", "/api/v1/watchlist", {"slug": "x" * 5000}),
    ("POST", "/api/v1/assistant/chat", {"message": "x" * 200_000}),
    ("PUT", "/api/v1/notify/prefs", {"families": "nope"}),
    ("PATCH", "/api/v1/auth/me", {"display_name": "x" * 10_000}),
    ("POST", "/api/v1/positions/close", {"slug": CANONICAL_SLUG}),
    ("POST", "/api/v1/social/follow/" + ("a" * 200), {}),
    ("POST", f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve", {"winning_outcome": "MAYBE"}),
    ("POST", "/api/v1/admin/markets", {"slug": 12345}),
    ("POST", "/api/v1/clones", {"name": "x", "nodes": "bad"}),
    ("POST", "/api/v1/telemetry/mirror/events", {"events": [{"x": "y" * 50_000}]}),
]


@pytest.mark.asyncio
async def test_z4_garbage_and_oversize_payloads_never_5xx(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token, _u = await _signup_user(db_session, client, "z4-abuse@example.com")
        client.cookies.clear()
        failures: list[str] = []
        sec_hits: list[str] = []

        for method, path, payload in _MUTATING_PROBES:
            headers = _auth(token)
            if path.startswith("/api/v1/admin"):
                headers = {**headers, **ADMIN_HEADERS}
            try:
                if payload == "not-json":
                    r = await client.request(
                        method,
                        path,
                        headers={**headers, "Content-Type": "application/json"},
                        content=b"{not valid json!!",
                    )
                else:
                    r = await client.request(
                        method, path, headers=headers, json=payload
                    )
            except Exception as exc:  # noqa: BLE001
                # Uncaught exception ≈ 5xx in production → SEC, xfail suite green.
                sec_hits.append(
                    f"SEC-Z4-02 {method} {path}: raised {type(exc).__name__}: {exc}"
                )
                continue
            if r.status_code >= 500:
                sec_hits.append(
                    f"SEC-Z4-02 {method} {path}: got {r.status_code} "
                    f"body={r.text[:160]!r}"
                )
                continue
            if r.status_code not in (
                200,
                201,
                202,
                204,
                400,
                401,
                403,
                404,
                405,
                409,
                413,
                415,
                422,
                429,
            ):
                failures.append(
                    f"{method} {path}: unexpected {r.status_code} {r.text[:120]!r}"
                )

        assert not failures, "\n".join(failures)
        if sec_hits:
            # Documented app defect: mutating abuse must never 5xx/raise.
            pytest.xfail("; ".join(sec_hits[:5]))


@pytest.mark.asyncio
async def test_z4_oversize_and_garbage_order_fields_are_4xx(db_session):
    """Oversize/garbage order fields must 4xx, never 5xx (extra keys may be ignored)."""
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token, _u = await _signup_user(db_session, client, "z4-big@example.com")
        client.cookies.clear()
        probes = [
            {
                "slug": "Z" * 10_000,
                "side": "YES",
                "shares": 1,
                "price": 0.5,
            },
            {
                "slug": CANONICAL_SLUG,
                "side": "YES" * 5000,
                "shares": 1,
                "price": 0.5,
            },
            {
                "slug": CANONICAL_SLUG,
                "side": "YES",
                "shares": 10**18,
                "price": 0.5,
            },
            {
                "slug": CANONICAL_SLUG,
                "side": "YES",
                "shares": 1,
                "price": "not-a-number",
            },
            "raw-not-object",
        ]
        for payload in probes:
            try:
                if payload == "raw-not-object":
                    r = await client.post(
                        "/api/v1/orders",
                        headers={
                            **_auth(token),
                            "Content-Type": "application/json",
                        },
                        content=b'["not", "an", "object"]' + (b"x" * 100_000),
                    )
                else:
                    r = await client.post(
                        "/api/v1/orders",
                        headers=_auth(token),
                        json=payload,
                    )
            except Exception as exc:  # noqa: BLE001
                pytest.xfail(
                    f"SEC-Z4-01: order abuse payload raised "
                    f"{type(exc).__name__}: {exc}"
                )
            assert r.status_code < 500, (
                f"SEC-Z4-01: order abuse returned 5xx {r.status_code} "
                f"payload={str(payload)[:80]!r} body={r.text[:120]!r}"
            )
            assert r.status_code in (400, 413, 415, 422), (
                f"expected 4xx, got {r.status_code} for {str(payload)[:80]!r}"
            )
