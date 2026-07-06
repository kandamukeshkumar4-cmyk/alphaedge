"""End-to-end user-journey smoke tests against a RUNNING AlphaEdge deployment.

Run with a base URL (local stack or the deployed demo):

    uv run --extra dev pytest tests/smoke/ -q --base-url http://127.0.0.1:8000
    uv run --extra dev pytest tests/smoke/ -q --base-url https://mukeshkumarkanda-alphaedge-api.hf.space

Covers the exact flows shown in demos: the public GET surface (no 5xx
anywhere), signup/login, paper trading through the RiskService path the
frontend uses, the AI analyst + assistant, and the signals/prediction
surfaces. Paper-trading only — tiny order sizes, positions closed after.

Set ALPHAEDGE_EXPECT_LLM=1 to make the AI-mode check a hard failure when the
deployment answers with the deterministic fallback instead of a real LLM.
"""

import os
import uuid
from collections.abc import Iterator

import httpx
import pytest

CANONICAL_SLUG = "nba-2025-01-15-lal-bos"


@pytest.fixture(scope="module")
def client(base_url: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=base_url, timeout=60.0) as http_client:
        yield http_client


@pytest.fixture(scope="module")
def auth_token(client: httpx.Client) -> str:
    """Sign up a throwaway smoke user and return its JWT."""
    email = f"smoke-{uuid.uuid4().hex[:12]}@alphaedge-smoke.com"
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "SmokeTest-123!", "name": "Smoke Journey"},
    )
    assert response.status_code in {200, 201}, response.text
    token = response.json().get("access_token")
    assert token, "signup did not return an access token"
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── 1. Public GET surface: nothing may 500 ──────────────────────────────────


def test_no_public_get_route_returns_5xx(client: httpx.Client) -> None:
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    substitutions = {
        "{slug}": CANONICAL_SLUG,
        "{account_id}": "00000000-0000-0000-0000-000000000001",
        "{market_id}": "00000000-0000-0000-0000-000000000001",
        "{brief_id}": "00000000-0000-0000-0000-000000000001",
        "{run_id}": "00000000-0000-0000-0000-000000000001",
        "{clone_id}": "00000000-0000-0000-0000-000000000001",
        "{external_market_id}": "00000000-0000-0000-0000-000000000001",
        "{order_id}": "00000000-0000-0000-0000-000000000001",
    }
    failures: list[str] = []
    for path, methods in sorted(spec.json()["paths"].items()):
        if "get" not in methods:
            continue
        url = path
        for placeholder, value in substitutions.items():
            url = url.replace(placeholder, value)
        if "{" in url:
            continue  # unknown placeholder — not sweepable
        response = client.get(url)
        if response.status_code >= 500:
            failures.append(f"{response.status_code} {path}: {response.text[:200]}")
    assert not failures, "GET routes returned server errors:\n" + "\n".join(failures)


# ── 2. Market data surface ──────────────────────────────────────────────────


def test_canonical_market_detail_candles_snapshot(client: httpx.Client) -> None:
    detail = client.get(f"/api/v1/markets/{CANONICAL_SLUG}/detail")
    assert detail.status_code == 200, detail.text
    candles = client.get(f"/api/v1/markets/{CANONICAL_SLUG}/candles")
    assert candles.status_code == 200, candles.text
    snapshot = client.get(f"/api/v1/markets/{CANONICAL_SLUG}/snapshot")
    assert snapshot.status_code == 200, snapshot.text
    assert snapshot.json().get("paper_trading_only") is True


def test_signals_surfaces(client: httpx.Client) -> None:
    for path in ("/api/v1/signals", "/api/v1/signals/events", "/api/v1/signals/feed"):
        response = client.get(path)
        assert response.status_code == 200, f"{path}: {response.text[:200]}"


# ── 3. Auth + paper trading (the frontend's exact order path) ───────────────


def test_auth_me_reports_paper_balance(client: httpx.Client, auth_token: str) -> None:
    me = client.get("/api/v1/auth/me", headers=_auth(auth_token))
    assert me.status_code == 200, me.text
    assert me.json()["paper_balance"] > 0


def test_paper_trade_lifecycle(client: httpx.Client, auth_token: str) -> None:
    """Buy → position appears in portfolio → close → realized PnL recorded."""
    headers = _auth(auth_token)
    order = client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "slug": CANONICAL_SLUG,
            "side": "buy",
            "outcome": "yes",
            "shares": 2,
            "price": 0.55,
        },
    )
    assert order.status_code in {200, 201}, order.text
    payload = order.json()
    assert payload["paper_trading_only"] is True
    assert payload["shares"] == 2

    portfolio = client.get("/api/v1/portfolio", headers=headers)
    assert portfolio.status_code == 200, portfolio.text
    positions = portfolio.json()["positions"]
    match = [p for p in positions if p["market_slug"] == CANONICAL_SLUG]
    assert match, f"expected an open {CANONICAL_SLUG} position, got {positions}"

    close = client.post(
        "/api/v1/positions/close",
        headers=headers,
        json={"slug": CANONICAL_SLUG, "outcome": "yes", "shares": 2, "price": 0.55},
    )
    assert close.status_code == 200, close.text
    assert close.json()["shares_sold"] == 2

    history = client.get("/api/v1/orders/history", headers=headers)
    assert history.status_code == 200, history.text


def test_portfolio_risk_and_summary(client: httpx.Client, auth_token: str) -> None:
    headers = _auth(auth_token)
    for path in ("/api/v1/portfolio/summary", "/api/v1/portfolio/risk", "/api/v1/portfolio/exposure"):
        response = client.get(path, headers=headers)
        assert response.status_code == 200, f"{path}: {response.text[:200]}"


# ── 4. AI analysis surface ──────────────────────────────────────────────────


def test_analyst_run_produces_brief_with_claim(client: httpx.Client) -> None:
    response = client.post(f"/api/v1/analyst/run?market_slug={CANONICAL_SLUG}")
    assert response.status_code == 200, response.text
    brief = response.json()
    assert brief["market_slug"] == CANONICAL_SLUG
    assert brief["headline"]
    assert brief["body_markdown"]
    assert brief["generator"] in {"llm", "fallback"}
    if os.environ.get("ALPHAEDGE_EXPECT_LLM") == "1":
        assert brief["generator"] == "llm", (
            "Deployment answered with the deterministic fallback — the LLM key is "
            "missing or the LLM call is failing (check API logs for "
            "'write_brief failed')."
        )

    listing = client.get("/api/v1/briefs", params={"limit": 5})
    assert listing.status_code == 200
    assert any(item["id"] == brief["id"] for item in listing.json()["items"])


def test_assistant_chat_answers_with_analysis_banner(client: httpx.Client) -> None:
    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Why did the Lakers vs Celtics odds move today?"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["reply"]
    assert payload["paper_trading_only"] is True
    assert "cannot place trades" in payload["analysis_only_banner"].lower()


def test_prediction_and_explain_endpoints(client: httpx.Client) -> None:
    prediction = client.get(f"/api/v1/markets/{CANONICAL_SLUG}/prediction")
    assert prediction.status_code == 200, prediction.text
    assert 0.0 <= prediction.json()["predicted_prob"] <= 1.0

    explain = client.get(f"/api/v1/markets/{CANONICAL_SLUG}/explain")
    assert explain.status_code == 200, explain.text
    assert explain.json()["trade_rationale"]


# ── 5. Track record / eval surface ──────────────────────────────────────────


def test_track_record_endpoints(client: httpx.Client) -> None:
    for path in (
        "/api/v1/analyst/track-record",
        "/api/v1/analyst/track-record/claims",
        "/api/v1/eval/aggregates",
        "/api/v1/calibration/latest",
    ):
        response = client.get(path)
        assert response.status_code == 200, f"{path}: {response.text[:200]}"


# ── 6. Agent harness (RiskService-gated pipeline proof) ─────────────────────


def test_agent_harness_run_is_risk_gated(client: httpx.Client) -> None:
    """Full agent pipeline on the canonical market: it must complete and the
    risk step must gate execution — no order artifacts on a weak edge.
    Requires ADMIN_API_KEY in the environment (defaults to the dev key)."""
    admin_key = os.environ.get("ADMIN_API_KEY", "dev-admin-key")
    response = client.post(
        f"/admin/agents/run/{CANONICAL_SLUG}",
        headers={"X-Admin-API-Key": admin_key},
    )
    if response.status_code in {401, 403}:
        pytest.skip("ADMIN_API_KEY not valid for this deployment")
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["market_slug"] == CANONICAL_SLUG
    assert run["status"] in {"blocked", "completed"}
    step_names = [step["step_name"] for step in run["steps"]]
    assert "risk" in step_names, f"agent run skipped the risk step: {step_names}"
    if run["approved"] is False:
        execute_steps = [s for s in run["steps"] if s["step_name"] == "execute"]
        execute_output = str([s.get("output_data") for s in execute_steps])
        assert "order_id" not in execute_output, (
            "risk-rejected agent run still produced an order artifact"
        )

    runs = client.get(
        "/admin/agents/runs", headers={"X-Admin-API-Key": admin_key}
    )
    assert runs.status_code == 200, runs.text
