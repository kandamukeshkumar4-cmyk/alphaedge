# STATE88A — K-A Kalshi WebSocket authentication

Status: DONE — K1–K3 implemented; the prior dependency block was cleared by
the orchestrator decision to add the approved `cryptography` runtime dependency.

## K1–K2 implementation

- K1 signs `timestamp + GET + path` with RSA-PSS-SHA256 and returns the three
  Kalshi access headers.
- K2 passes those headers to the Kalshi-only WebSocket connector when both
  `KALSHI_API_KEY_ID` and `KALSHI_SIGNING_PEM` are non-empty.
- Empty credentials preserve the unauthenticated connector behavior and REST
  polling remains available as the paper-trading fallback.

## RUNBOOK

Set these exact Railway variables to re-enable authenticated Kalshi WebSocket
ingest (do not commit secret values):

```text
KALSHI_API_KEY_ID=<Kalshi API key id>
KALSHI_SIGNING_PEM=<Kalshi RSA private key PEM>
KALSHI_WS_ENABLED=true
```

The signature path must exactly match the path in `KALSHI_WS_URL`. The default
URL path is `/trade-api/ws/v2`; if `KALSHI_WS_URL` is changed, the helper signs
that URL's path instead. A path mismatch causes Kalshi to reject the upgrade
with HTTP 401.

Rollback: set `KALSHI_WS_ENABLED=false` in Railway. This leaves REST live
polling enabled and stops the WebSocket reconnect loop without changing any
code or environment defaults.

## Verification record

- K1: `tests/test_kalshi_auth.py` — 3 passed; Ruff passed.
- K2: `tests/test_kalshi_auth.py` — 5 passed; Ruff passed.
- No migrations, cash funding, external execution, push, or deploy actions.
