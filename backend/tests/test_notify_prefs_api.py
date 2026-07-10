"""L03 — notification preferences store tests.

AUTHED (JWT). Per-user opt-in set of alert families. STORED + read in-app only —
NO external delivery. Default (no stored row) = all families on. 401 anon.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.notify_prefs import ALERT_FAMILIES
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _signup_token(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "securepass1"}
    )
    assert r.status_code == 201
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_anon_get_is_401(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/v1/notify/prefs")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_anon_put_is_401(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.put(
            "/api/v1/notify/prefs", json={"families": ["arb"]}
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_default_all_on_first_read(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token = await _signup_token(client, "prefs-default@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.get("/api/v1/notify/prefs", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "default"
    assert body["enabled"] == list(ALERT_FAMILIES)
    assert all(body["families"][f] is True for f in ALERT_FAMILIES)
    assert body["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_put_round_trips(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token = await _signup_token(client, "prefs-rt@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        put = await client.put(
            "/api/v1/notify/prefs",
            json={"families": ["arb", "news:mispricing"]},
            headers=headers,
        )
        assert put.status_code == 200
        assert put.json()["source"] == "stored"
        # Enabled echoed in canonical family order.
        assert put.json()["enabled"] == ["news:mispricing", "arb"]

        get = await client.get("/api/v1/notify/prefs", headers=headers)
    body = get.json()
    assert body["source"] == "stored"
    assert body["enabled"] == ["news:mispricing", "arb"]
    assert body["families"]["delta:*"] is False
    assert body["families"]["arb"] is True


@pytest.mark.asyncio
async def test_put_empty_opts_out_of_all(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token = await _signup_token(client, "prefs-empty@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        put = await client.put(
            "/api/v1/notify/prefs", json={"families": []}, headers=headers
        )
        assert put.status_code == 200
        get = await client.get("/api/v1/notify/prefs", headers=headers)
    body = get.json()
    assert body["source"] == "stored"
    assert body["enabled"] == []
    assert all(body["families"][f] is False for f in ALERT_FAMILIES)


@pytest.mark.asyncio
async def test_invalid_family_rejected(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token = await _signup_token(client, "prefs-invalid@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.put(
            "/api/v1/notify/prefs",
            json={"families": ["arb", "not-a-family"]},
            headers=headers,
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_per_user_isolation(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        tok_a = await _signup_token(client, "prefs-iso-a@example.com")
        tok_b = await _signup_token(client, "prefs-iso-b@example.com")
        head_a = {"Authorization": f"Bearer {tok_a}"}
        head_b = {"Authorization": f"Bearer {tok_b}"}

        await client.put(
            "/api/v1/notify/prefs", json={"families": ["arb"]}, headers=head_a
        )
        # B never set prefs → still the default (all on).
        b = await client.get("/api/v1/notify/prefs", headers=head_b)
        a = await client.get("/api/v1/notify/prefs", headers=head_a)
    assert b.json()["source"] == "default"
    assert b.json()["enabled"] == list(ALERT_FAMILIES)
    assert a.json()["source"] == "stored"
    assert a.json()["enabled"] == ["arb"]
