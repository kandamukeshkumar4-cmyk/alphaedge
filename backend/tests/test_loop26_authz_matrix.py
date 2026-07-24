"""Loop V26 Z1 — AuthZ matrix over the OpenAPI surface snapshot.

Walks ``tests/fixtures/openapi_snapshot.json`` (154 paths / 167 operations)
and asserts each operation's response under three actors:

* anonymous (no credentials)
* user JWT (Bearer from signup)
* admin key (``X-Admin-API-Key: dev-admin-key``)

Expected status codes are drawn from an explicit route→auth-class table built
by reading router ``Depends`` graphs (``verify_admin_api_key``,
``get_current_user``, ``get_optional_user``, plus the special ``/metrics``
inline admin gate). Allowed classes only: 2xx / 401 / 403 / 404 / 405 / 422
(plus common client errors 400 / 409). **No 5xx ever.**

App-code defects are NOT fixed here — they become SEC REPORT entries in
``goals/loop-v26-authz/STATE.md``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import ratelimit
from app.db.session import get_db
from app.main import app

SNAPSHOT_PATH = Path(__file__).parent / "fixtures" / "openapi_snapshot.json"
METHODS = ("get", "post", "put", "patch", "delete")

# ---------------------------------------------------------------------------
# Route → expected auth class (from reading routers / FastAPI dep graph)
# ---------------------------------------------------------------------------
# admin          = Depends(verify_admin_api_key)  — missing key → 422, bad → 401
# admin_metrics  = GET /metrics inline gate      — missing/wrong → 401
# user           = Depends(get_current_user)      — missing/invalid → 401
# optional_user  = Depends(get_optional_user)     — anonymous allowed
# public         = no user/admin dependency        (may still check paper token)
# ---------------------------------------------------------------------------
AUTH_CLASS: dict[tuple[str, str], str] = {
    ("get", "/api/v1/markets/{slug}/indicators"): "public",
    ("get", "/api/v1/alpha/factors"): "public",
    ("get", "/api/v1/alpha/latest-signal"): "public",
    ("get", "/api/v1/alpha/report"): "public",
    ("get", "/api/v1/alpha/runs"): "public",
    ("delete", "/api/v1/clones/{clone_id}"): "user",
    ("delete", "/api/v1/social/follow/{trader}"): "user",
    ("delete", "/api/v1/watchlist/{slug}"): "user",
    ("get", "/"): "public",
    ("get", "/admin/agents/runs"): "admin",
    ("get", "/admin/agents/runs/{run_id}"): "admin",
    ("get", "/admin/historical-closing-snapshot-captures"): "admin",
    ("get", "/admin/market-snapshot-captures"): "admin",
    ("get", "/admin/phase3-snapshot-store-backtests"): "admin",
    ("get", "/admin/smoke-account"): "admin",
    ("get", "/api/v1/accounts/{account_id}/positions"): "public",
    ("get", "/api/v1/activity/trades"): "public",
    ("get", "/api/v1/admin/dogfood/mirror-report"): "admin",
    ("get", "/api/v1/admin/jobs"): "admin",
    ("get", "/api/v1/admin/markets"): "admin",
    ("get", "/api/v1/admin/observability/drift"): "admin",
    ("get", "/api/v1/admin/observability/slo"): "admin",
    ("get", "/api/v1/admin/observability/summary"): "admin",
    ("get", "/api/v1/admin/observability/traces"): "admin",
    ("get", "/api/v1/admin/stats"): "admin",
    ("get", "/api/v1/admin/users"): "admin",
    ("get", "/api/v1/admin/users/{user_id}"): "admin",
    ("get", "/api/v1/admin/wc2026/status"): "admin",
    ("get", "/api/v1/alerts"): "public",
    ("get", "/api/v1/alerts/digest"): "public",
    ("get", "/api/v1/alerts/feed"): "optional_user",
    ("get", "/api/v1/analyst/track-record"): "public",
    ("get", "/api/v1/analyst/track-record/claims"): "public",
    ("get", "/api/v1/arb/opportunities"): "public",
    ("get", "/api/v1/auth/me"): "user",
    ("get", "/api/v1/backfill/markets"): "public",
    ("get", "/api/v1/backtest/run"): "public",
    ("get", "/api/v1/backtest/runs"): "public",
    ("get", "/api/v1/backtest/runs/{run_id}"): "public",
    ("get", "/api/v1/backtest/summary"): "public",
    ("get", "/api/v1/briefs"): "public",
    ("get", "/api/v1/briefs/{brief_id}"): "public",
    ("get", "/api/v1/calibration/latest"): "public",
    ("get", "/api/v1/categories/{category}/summary"): "public",
    ("get", "/api/v1/clones"): "user",
    ("get", "/api/v1/clones/leaderboard"): "public",
    ("get", "/api/v1/clones/nodes"): "public",
    ("get", "/api/v1/clones/{clone_id}"): "user",
    ("get", "/api/v1/clones/{clone_id}/runs"): "user",
    ("get", "/api/v1/clones/{clone_id}/scorecard"): "public",
    ("get", "/api/v1/clones/{clone_id}/versions"): "user",
    ("get", "/api/v1/clv-track-record"): "public",
    ("get", "/api/v1/compare"): "public",
    ("get", "/api/v1/desk"): "public",
    ("get", "/api/v1/eval/aggregates"): "public",
    ("get", "/api/v1/eval/calibration"): "public",
    ("get", "/api/v1/eval/drift"): "public",
    ("get", "/api/v1/eval/evaluations"): "public",
    ("get", "/api/v1/feed"): "public",
    ("get", "/api/v1/forecasters/me/dashboard"): "public",
    ("get", "/api/v1/forecasters/me/forecast-lifecycle"): "public",
    ("get", "/api/v1/health/detailed"): "public",
    ("get", "/api/v1/home"): "optional_user",
    ("get", "/api/v1/leaderboard"): "public",
    ("get", "/api/v1/macro"): "public",
    ("get", "/api/v1/markets"): "public",
    ("get", "/api/v1/markets/{slug}"): "public",
    ("get", "/api/v1/markets/{slug}/agent-trace"): "public",
    ("get", "/api/v1/markets/{slug}/book"): "public",
    ("get", "/api/v1/markets/{slug}/candles"): "public",
    ("get", "/api/v1/markets/{slug}/detail"): "public",
    ("get", "/api/v1/markets/{slug}/drivers"): "public",
    ("get", "/api/v1/markets/{slug}/edge-history"): "public",
    ("get", "/api/v1/markets/{slug}/explain"): "public",
    ("get", "/api/v1/markets/{slug}/history"): "public",
    ("get", "/api/v1/markets/{slug}/latency"): "public",
    ("get", "/api/v1/markets/{slug}/prediction"): "public",
    ("get", "/api/v1/markets/{slug}/prices/latest"): "public",
    ("get", "/api/v1/markets/{slug}/share-snapshot"): "public",
    ("get", "/api/v1/markets/{slug}/signals"): "public",
    ("get", "/api/v1/markets/{slug}/snapshot"): "public",
    ("get", "/api/v1/memories"): "public",
    ("get", "/api/v1/models"): "admin",
    ("get", "/api/v1/notifications"): "user",
    ("get", "/api/v1/notify/prefs"): "user",
    ("get", "/api/v1/opportunities"): "public",
    ("get", "/api/v1/orders"): "public",
    ("get", "/api/v1/orders/history"): "user",
    ("get", "/api/v1/paper-account"): "public",
    ("get", "/api/v1/portfolio"): "user",
    ("get", "/api/v1/portfolio/attribution"): "user",
    ("get", "/api/v1/portfolio/clv-summary"): "user",
    ("get", "/api/v1/portfolio/equity-curve"): "user",
    ("get", "/api/v1/portfolio/exposure"): "user",
    ("get", "/api/v1/portfolio/risk"): "user",
    ("get", "/api/v1/portfolio/summary"): "user",
    ("get", "/api/v1/profile"): "user",
    ("get", "/api/v1/resolved"): "public",
    ("get", "/api/v1/search"): "public",
    ("get", "/api/v1/signals"): "public",
    ("get", "/api/v1/signals/arbitrage"): "public",
    ("get", "/api/v1/signals/dashboard"): "public",
    ("get", "/api/v1/signals/dutching"): "public",
    ("get", "/api/v1/signals/events"): "public",
    ("get", "/api/v1/signals/feed"): "public",
    ("get", "/api/v1/signals/forecast"): "public",
    ("get", "/api/v1/signals/screeners"): "public",
    ("get", "/api/v1/signals/smart-money"): "public",
    ("get", "/api/v1/smart-money"): "public",
    ("get", "/api/v1/social/feed"): "user",
    ("get", "/api/v1/social/following"): "user",
    ("get", "/api/v1/social/traders/{trader}"): "public",
    ("get", "/api/v1/sports/results"): "public",
    ("get", "/api/v1/system/loops"): "public",
    ("get", "/api/v1/system/metrics"): "public",
    ("get", "/api/v1/system/model-ab"): "public",
    ("get", "/api/v1/system/resolved-count"): "public",
    ("get", "/api/v1/system/sources"): "admin",
    ("get", "/api/v1/track-record"): "public",
    ("get", "/api/v1/watchlist"): "user",
    ("get", "/api/v1/watchlist/alerts"): "user",
    ("get", "/api/v1/wc2026/schedule"): "public",
    ("get", "/api/v1/weather/edges"): "public",
    ("get", "/health"): "public",
    ("get", "/metrics"): "admin_metrics",
    ("patch", "/api/v1/admin/markets/{slug}"): "admin",
    ("patch", "/api/v1/auth/me"): "user",
    ("patch", "/api/v1/clones/{clone_id}"): "user",
    ("post", "/admin/agents/run/{slug}"): "admin",
    ("post", "/admin/historical-closing-snapshot-captures"): "admin",
    ("post", "/admin/markets"): "admin",
    ("post", "/admin/markets/{market_id}/lock"): "admin",
    ("post", "/admin/markets/{market_id}/resolve"): "admin",
    ("post", "/admin/phase3-snapshot-store-backtests"): "admin",
    ("post", "/api/v1/admin/external-markets/{external_market_id}/resolve"): "admin",
    ("post", "/api/v1/admin/markets"): "admin",
    ("post", "/api/v1/admin/markets/{slug}/cancel"): "admin",
    ("post", "/api/v1/admin/markets/{slug}/pause"): "admin",
    ("post", "/api/v1/admin/markets/{slug}/resolve"): "admin",
    ("post", "/api/v1/admin/markets/{slug}/unpause"): "admin",
    ("post", "/api/v1/admin/users/{user_id}/suspend"): "admin",
    ("post", "/api/v1/admin/users/{user_id}/unsuspend"): "admin",
    ("post", "/api/v1/admin/wc2026/resolve"): "admin",
    ("post", "/api/v1/admin/wc2026/seed"): "admin",
    ("post", "/api/v1/analyst/run"): "user",
    ("post", "/api/v1/arb/detect"): "public",
    ("post", "/api/v1/assistant/chat"): "optional_user",
    ("post", "/api/v1/auth/login"): "public",
    ("post", "/api/v1/auth/logout"): "public",
    ("post", "/api/v1/auth/signup"): "public",
    ("post", "/api/v1/backtest/run"): "user",
    ("post", "/api/v1/clones"): "user",
    ("post", "/api/v1/clones/{clone_id}/run"): "user",
    ("post", "/api/v1/forecasters/anonymous"): "public",
    ("post", "/api/v1/forecasters/me/recovery"): "public",
    ("post", "/api/v1/forecasters/recover"): "public",
    ("post", "/api/v1/forecasts"): "public",
    ("post", "/api/v1/markets/external/resolve-url"): "public",
    ("post", "/api/v1/markets/{slug}/orders"): "public",
    ("post", "/api/v1/markets/{slug}/signals"): "public",
    ("post", "/api/v1/models/rollback"): "admin",
    ("post", "/api/v1/models/{version_id}/activate"): "admin",
    ("post", "/api/v1/notifications/read-all"): "user",
    ("post", "/api/v1/notifications/{notification_id}/read"): "user",
    ("post", "/api/v1/orders"): "user",
    ("post", "/api/v1/orders/{order_id}/cancel"): "public",
    ("post", "/api/v1/positions/close"): "user",
    ("post", "/api/v1/social/follow/{trader}"): "user",
    ("post", "/api/v1/sports/ingest"): "admin",
    ("post", "/api/v1/telemetry/mirror/events"): "public",
    ("post", "/api/v1/watchlist"): "user",
    ("put", "/api/v1/notify/prefs"): "user",
    # Loop V58–V92 snapshot additions: classifications mirror handler dependencies.
    ("get", "/api/v1/context/digest"): "public",
    ("get", "/api/v1/heartbeat/decisions"): "public",
    ("get", "/api/v1/markets/{slug}/context"): "public",
    ("get", "/api/v1/markets/{slug}/locked-forecast"): "public",
    ("get", "/api/v1/notifications/preferences"): "user",
    ("put", "/api/v1/notifications/preferences"): "user",
    ("post", "/api/v1/notifications/push/subscribe"): "user",
    ("get", "/api/v1/pods"): "public",
    ("get", "/api/v1/portfolio/analytics"): "user",
    ("get", "/api/v1/scanners/"): "public",
    ("post", "/api/v1/scanners/"): "user",
    ("post", "/api/v1/scanners/compile"): "public",
    ("get", "/api/v1/scanners/featured"): "public",
    ("get", "/api/v1/scanners/trending"): "public",
    ("get", "/api/v1/scanners/{scanner_id}"): "public",
    ("patch", "/api/v1/scanners/{scanner_id}"): "user",
    ("post", "/api/v1/scanners/{scanner_id}/feature"): "admin",
    ("post", "/api/v1/scanners/{scanner_id}/fork"): "user",
    ("post", "/api/v1/scanners/{scanner_id}/pause"): "user",
    ("post", "/api/v1/scanners/{scanner_id}/publish"): "user",
    ("post", "/api/v1/scanners/{scanner_id}/rate"): "user",
    ("post", "/api/v1/scanners/{scanner_id}/resume"): "user",
    ("post", "/api/v1/scanners/{scanner_id}/rollback"): "user",
    ("post", "/api/v1/scanners/{scanner_id}/run"): "user",
    ("get", "/api/v1/scanners/{scanner_id}/runs"): "public",
    ("post", "/api/v1/scanners/{scanner_id}/test-email"): "user",
    ("post", "/api/v1/scanners/{scanner_id}/test-run"): "user",
    ("get", "/api/v1/screener"): "public",
    ("get", "/api/v1/skills/"): "public",
    ("post", "/api/v1/skills/"): "user",
    ("get", "/api/v1/skills/featured"): "public",
    ("get", "/api/v1/skills/trending"): "public",
    ("get", "/api/v1/skills/{skill_id}"): "public",
    ("post", "/api/v1/skills/{skill_id}/feature"): "admin",
    ("post", "/api/v1/skills/{skill_id}/fork"): "user",
    ("post", "/api/v1/skills/{skill_id}/rate"): "user",
    ("post", "/api/v1/skills/{skill_id}/run"): "user",
    ("get", "/api/v1/subscriptions/"): "user",
    ("post", "/api/v1/subscriptions/"): "user",
    ("delete", "/api/v1/subscriptions/{ref_type}/{ref_id}"): "user",
    ("get", "/api/v1/terminal/sessions"): "user",
    ("post", "/api/v1/terminal/sessions"): "user",
    ("get", "/api/v1/terminal/sessions/{session_id}"): "user",
    ("delete", "/api/v1/terminal/sessions/{session_id}"): "user",
    ("post", "/api/v1/terminal/sessions/{session_id}/execute"): "user",
    ("post", "/api/v1/terminal/sessions/{session_id}/resume"): "user",
    ("post", "/api/v1/terminal/sessions/{session_id}/save-as-skill"): "user",
    ("get", "/api/v1/terminal/sessions/{session_id}/stream"): "user",
    ("get", "/api/v1/usage/summary"): "public",
    ("get", "/api/v1/venue-gaps"): "public",
}

# Path-param fillers for live probes (honest empty / not-found paths preferred).
_PATH_VALUES: dict[str, str] = {
    "slug": "nba-2025-01-15-lal-bos",
    "market_id": "00000000-0000-0000-0000-0000000000aa",
    "user_id": "00000000-0000-0000-0000-0000000000bb",
    "order_id": "00000000-0000-0000-0000-0000000000cc",
    "clone_id": "00000000-0000-0000-0000-0000000000dd",
    "brief_id": "00000000-0000-0000-0000-0000000000ee",
    "notification_id": "00000000-0000-0000-0000-0000000000ff",
    "run_id": "00000000-0000-0000-0000-000000000011",
    "account_id": "00000000-0000-0000-0000-000000000001",
    "external_market_id": "00000000-0000-0000-0000-000000000022",
    "version_id": "00000000-0000-0000-0000-000000000033",
    "scanner_id": "00000000-0000-0000-0000-000000000044",
    "skill_id": "00000000-0000-0000-0000-000000000055",
    "session_id": "00000000-0000-0000-0000-000000000066",
    "ref_type": "scanner",
    "ref_id": "00000000-0000-0000-0000-000000000077",
    "trader": "unknown-trader",
    "category": "Sports",
}

_PARAM_RE = re.compile(r"\{([^{}/]+)\}")

# Universe of non-5xx codes this matrix accepts for any probe.
_PERMITTED = frozenset({200, 201, 202, 204, 400, 401, 403, 404, 405, 409, 422, 429})


def _snapshot_ops() -> list[tuple[str, str]]:
    snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    ops: list[tuple[str, str]] = []
    for path, methods in sorted(snap.items()):
        for method in METHODS:
            if method in methods:
                ops.append((method, path))
    return ops


def _materialize(path: str) -> str:
    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in _PATH_VALUES:
            raise AssertionError(f"no path filler for {{{name}}} in {path}")
        return _PATH_VALUES[name]

    return _PARAM_RE.sub(repl, path)


def _query_for(method: str, path: str) -> dict[str, str]:
    """Supply required query params so probes exercise auth, not missing-params."""
    q: dict[str, str] = {}
    if path == "/api/v1/orders":
        q["account_id"] = _PATH_VALUES["account_id"]
    if path == "/api/v1/desk":
        q["slug"] = _PATH_VALUES["slug"]
    if path == "/api/v1/compare":
        q["a"] = _PATH_VALUES["slug"]
        q["b"] = "guard-open-no-candles"
    if path == "/api/v1/search":
        q["q"] = "lakers"
    if path.endswith("/resolve-url") or path == "/api/v1/markets/external/resolve-url":
        q["url"] = "https://example.com/market"
    return q


def _json_body(method: str, path: str) -> dict[str, Any] | None:
    if method not in ("post", "put", "patch"):
        return None
    # Minimal bodies — validation 422 is fine; we care about auth + no 5xx.
    if path == "/api/v1/auth/signup":
        return {"email": "z1-matrix-unique@example.com", "password": "securepass1"}
    if path == "/api/v1/auth/login":
        return {"email": "nobody@example.com", "password": "wrong-password-xx"}
    if path == "/api/v1/orders":
        return {
            "slug": _PATH_VALUES["slug"],
            "side": "YES",
            "shares": 1,
            "price": 0.5,
        }
    if path == "/api/v1/assistant/chat":
        return {"message": "ping"}
    if path == "/api/v1/watchlist":
        return {"slug": _PATH_VALUES["slug"]}
    if path == "/api/v1/notify/prefs":
        return {}
    if path == "/api/v1/auth/me":
        return {}
    if path == "/api/v1/positions/close":
        return {"slug": _PATH_VALUES["slug"], "side": "YES"}
    if path.endswith("/orders"):
        return {
            "account_id": _PATH_VALUES["account_id"],
            "side": "YES",
            "price": 0.5,
            "quantity": 1,
        }
    if path.endswith("/cancel") and "orders" in path:
        return {"account_id": _PATH_VALUES["account_id"]}
    if path == "/api/v1/admin/markets" or path == "/admin/markets":
        return {
            "slug": "z1-matrix-mkt",
            "title": "Z1",
            "question": "Z1?",
        }
    if "resolve" in path:
        return {"winning_outcome": "YES"}
    return {}


def _headers_for(actor: str, user_token: str) -> dict[str, str]:
    if actor == "anon":
        return {}
    if actor == "user":
        return {"Authorization": f"Bearer {user_token}"}
    if actor == "admin":
        return {"X-Admin-API-Key": "dev-admin-key"}
    raise AssertionError(actor)


def _expected_codes(auth_class: str, actor: str) -> frozenset[int]:
    """Auth-gate expectations per class × actor.

    After the gate, business/validation codes (2xx/404/422/…) remain permitted
    for authorized actors via ``_PERMITTED`` intersection in the assertion.
    """
    if auth_class == "admin":
        if actor in ("anon", "user"):
            # Header(..., alias=X-Admin-API-Key) → 422 when absent.
            return frozenset({401, 422})
        # Valid admin key: auth passes; resource may 2xx/404/422/409/400.
        return frozenset({200, 201, 202, 204, 400, 404, 405, 409, 422})
    if auth_class == "admin_metrics":
        if actor in ("anon", "user"):
            return frozenset({401})
        return frozenset({200, 201, 202, 204})
    if auth_class == "user":
        if actor in ("anon", "admin"):
            # Admin key alone is not a user JWT.
            return frozenset({401})
        return frozenset({200, 201, 202, 204, 400, 403, 404, 405, 409, 422})
    # public + optional_user: any permitted non-5xx (incl. paper-token 401).
    return _PERMITTED


def _load_ops() -> list[tuple[str, str, str]]:
    ops = _snapshot_ops()
    rows: list[tuple[str, str, str]] = []
    missing: list[tuple[str, str]] = []
    for method, path in ops:
        auth = AUTH_CLASS.get((method, path))
        if auth is None:
            missing.append((method, path))
            continue
        rows.append((method, path, auth))
    if missing:
        raise AssertionError(f"AUTH_CLASS missing snapshot ops: {missing}")
    extra = sorted(set(AUTH_CLASS) - set(ops))
    if extra:
        raise AssertionError(f"AUTH_CLASS has ops not in snapshot: {extra}")
    return rows


_OPS = _load_ops()


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    ratelimit.reset()
    yield
    app.dependency_overrides.clear()
    ratelimit.reset()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Keep the matrix offline — stub request-time connectors."""
    try:
        from app.data.connectors.fred import FredConnector

        monkeypatch.setattr(FredConnector, "fetch_indicators", lambda self: [])
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.services.weather_desk import WeatherDeskService

        monkeypatch.setattr(WeatherDeskService, "scan", lambda self, day: [])
    except Exception:  # noqa: BLE001
        pass


def test_auth_class_table_covers_snapshot_surface():
    """197 paths in the snapshot; every operation has an auth class."""
    snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert len(snap) == 202, f"expected 202 paths, got {len(snap)}"
    assert len(_OPS) == 222, f"expected 222 ops, got {len(_OPS)}"
    counts: dict[str, int] = {}
    for _m, _p, auth in _OPS:
        counts[auth] = counts.get(auth, 0) + 1
    assert counts["admin"] == 41
    assert counts["user"] == 66
    assert counts["optional_user"] == 3
    assert counts["admin_metrics"] == 1
    assert counts["public"] == 111


# Soft-checked app defects (must still not be uncaught). Loop V27 cleared
# SEC-Z1-01 (phase3 body validation + empty-matrix blocked result).
_XFAIL_PROBES: dict[tuple[str, str, str], str] = {}


@pytest.mark.asyncio
async def test_authz_matrix_walks_openapi_snapshot(db_session):
    """Each snapshot op × {anon, user, admin} → expected auth class, never 5xx."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        signup = await client.post(
            "/api/v1/auth/signup",
            json={"email": "z1-matrix-walker@example.com", "password": "securepass1"},
        )
        assert signup.status_code == 201, signup.text
        user_token = signup.json()["access_token"]
        # Signup sets httpOnly ae_access cookie — clear so "anon" is truly anonymous.
        client.cookies.clear()

        failures: list[str] = []
        sec_hits: list[str] = []
        for method, path, auth_class in _OPS:
            url = _materialize(path)
            params = _query_for(method, path)
            body = _json_body(method, path)
            for actor in ("anon", "user", "admin"):
                # Never leak the signup cookie into subsequent probes.
                client.cookies.clear()
                headers = _headers_for(actor, user_token)
                label = f"{method.upper()} {path} actor={actor} auth={auth_class}"
                xfail_sec = _XFAIL_PROBES.get((method, path, actor))
                try:
                    response = await client.request(
                        method.upper(),
                        url,
                        headers=headers,
                        params=params or None,
                        json=body,
                    )
                except Exception as exc:  # noqa: BLE001
                    # Uncaught handler exceptions ≈ 5xx in real deploys.
                    msg = (
                        f"{label}: raised {type(exc).__name__}: {exc} "
                        f"(treat as 5xx)"
                    )
                    if xfail_sec:
                        sec_hits.append(f"{xfail_sec}: {msg}")
                    else:
                        failures.append(msg)
                    continue
                code = response.status_code
                if code >= 500:
                    msg = f"{label}: got {code} (5xx forbidden) body={response.text[:180]!r}"
                    if xfail_sec:
                        sec_hits.append(f"{xfail_sec}: {msg}")
                    else:
                        failures.append(msg)
                    continue
                if code not in _PERMITTED:
                    failures.append(
                        f"{label}: got {code} outside permitted set "
                        f"body={response.text[:180]!r}"
                    )
                    continue
                expected = _expected_codes(auth_class, actor)
                if code not in expected:
                    failures.append(
                        f"{label}: got {code}, expected one of {sorted(expected)} "
                        f"body={response.text[:180]!r}"
                    )

        assert not failures, (
            f"{len(failures)} authz matrix failure(s):\n"
            + "\n".join(failures[:80])
            + (f"\n... and {len(failures) - 80} more" if len(failures) > 80 else "")
        )
        # Every soft-checked probe must actually fire (else the SEC id is stale).
        assert len(sec_hits) == len(_XFAIL_PROBES), (
            f"expected {len(_XFAIL_PROBES)} documented SEC hit(s), got {len(sec_hits)}: "
            f"{sec_hits}"
        )
