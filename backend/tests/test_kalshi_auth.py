"""Kalshi WebSocket authentication contract tests."""
from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.data.streams.kalshi_ws import KalshiMarketStream


@pytest.fixture
def rsa_key_pair() -> tuple[rsa.RSAPrivateKey, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    return private_key, pem


def test_build_headers_signature_verifies(rsa_key_pair):
    from app.data.streams.kalshi_auth import build_kalshi_ws_headers

    private_key, pem = rsa_key_pair
    timestamp = 1_700_000_000_123
    path = "/trade-api/ws/v2"

    headers = build_kalshi_ws_headers("key-id", pem, path, now_ms=timestamp)

    assert set(headers) == {
        "KALSHI-ACCESS-KEY",
        "KALSHI-ACCESS-TIMESTAMP",
        "KALSHI-ACCESS-SIGNATURE",
    }
    assert headers["KALSHI-ACCESS-KEY"] == "key-id"
    assert headers["KALSHI-ACCESS-TIMESTAMP"] == str(timestamp)

    private_key.public_key().verify(
        base64.b64decode(headers["KALSHI-ACCESS-SIGNATURE"]),
        f"{timestamp}GET{path}".encode("utf-8"),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=hashes.SHA256().digest_size,
        ),
        hashes.SHA256(),
    )


@pytest.mark.parametrize(
    ("key_id", "pem"),
    [("", "private-key"), ("key-id", "")],
)
def test_build_headers_rejects_empty_credentials(key_id, pem):
    from app.data.streams.kalshi_auth import build_kalshi_ws_headers

    with pytest.raises(ValueError):
        build_kalshi_ws_headers(key_id, pem, "/trade-api/ws/v2", now_ms=1)


@pytest.mark.asyncio
async def test_kalshi_connect_adds_headers_when_credentials_are_set(
    monkeypatch, rsa_key_pair
):
    private_key, pem = rsa_key_pair
    captured: dict = {}

    async def fake_connect(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    import websockets

    monkeypatch.setattr(websockets, "connect", fake_connect)
    stream = KalshiMarketStream(
        {"TICKER": "slug"},
        ws_url="wss://example.test/trade-api/ws/v2",
        api_key_id="key-id",
        signing_pem=pem,
    )

    await stream._connect()

    assert captured["url"] == "wss://example.test/trade-api/ws/v2"
    headers = captured["kwargs"]["additional_headers"]
    assert headers["KALSHI-ACCESS-KEY"] == "key-id"
    private_key.public_key().verify(
        base64.b64decode(headers["KALSHI-ACCESS-SIGNATURE"]),
        f'{headers["KALSHI-ACCESS-TIMESTAMP"]}GET/trade-api/ws/v2'.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=hashes.SHA256().digest_size,
        ),
        hashes.SHA256(),
    )


@pytest.mark.asyncio
async def test_kalshi_connect_omits_headers_without_credentials(monkeypatch):
    captured: dict = {}

    async def fake_connect(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    import websockets

    monkeypatch.setattr(websockets, "connect", fake_connect)
    await KalshiMarketStream({"TICKER": "slug"})._connect()

    assert captured["kwargs"] == {
        "open_timeout": 15,
        "max_size": 8 * 1024 * 1024,
    }
