"""Authentication helpers for the Kalshi WebSocket API."""
from __future__ import annotations

import base64
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def build_kalshi_ws_headers(
    key_id: str,
    pem: str,
    path: str,
    now_ms: int | None = None,
) -> dict[str, str]:
    """Build the RSA-PSS authentication headers for a Kalshi WS handshake."""
    if not key_id or not pem:
        raise ValueError("Kalshi API key id and signing PEM are required")

    try:
        private_key = serialization.load_pem_private_key(
            pem.encode("utf-8"), password=None
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Kalshi signing PEM is invalid") from exc
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise ValueError("Kalshi signing PEM must contain an RSA private key")

    timestamp = str(now_ms if now_ms is not None else int(time.time() * 1000))
    message = f"{timestamp}GET{path}".encode("utf-8")
    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=hashes.SHA256().digest_size,
        ),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode("ascii"),
    }
