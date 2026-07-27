import pytest

from app.services.market_service import CATALOG_SLUGS

REQUIRED_FIELDS = (
    "slug",
    "available",
    "predicted_prob",
    "confidence",
    "edge",
    "is_edge",
    "reason",
    "provisional",
    "market_implied",
    "price_source",
    "paper_trading_only",
)

NBA_SLUG = "nba-2025-01-15-lal-bos"
FIFA_SLUG = "wc2026-m1-mex-homewin"


@pytest.mark.asyncio
async def test_unknown_slug_returns_404(catalog_api_client):
    response = await catalog_api_client.get(
        "/api/v1/markets/unknown-market-slug/prediction"
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_valid_nba_slug_returns_prediction(catalog_api_client):
    response = await catalog_api_client.get(f"/api/v1/markets/{NBA_SLUG}/prediction")

    assert response.status_code == 200
    payload = response.json()
    assert payload["paper_trading_only"] is True
    assert 0.0 <= payload["predicted_prob"] <= 1.0


@pytest.mark.asyncio
async def test_valid_fifa_slug_is_provisional(catalog_api_client):
    response = await catalog_api_client.get(f"/api/v1/markets/{FIFA_SLUG}/prediction")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provisional"] is True


@pytest.mark.asyncio
async def test_response_has_all_required_fields(catalog_api_client):
    response = await catalog_api_client.get(f"/api/v1/markets/{NBA_SLUG}/prediction")

    assert response.status_code == 200
    payload = response.json()
    for field in REQUIRED_FIELDS:
        assert field in payload


@pytest.mark.asyncio
async def test_ensemble_absent_falls_back_to_baseline(catalog_api_client, monkeypatch):
    """Flag ON but no LLM keys -> ensemble degrades to None, the response is the
    exact single-model baseline (fallback proof).

    Enforce the "no keys" precondition explicitly by clearing every provider key
    on the shared settings object, so the test is hermetic: it proves the
    degradation path regardless of whatever LLM keys a developer's ``.env``
    happens to configure (CI has none; a live dev box may have a real NIM key).
    """
    import app.api.v1.market_prediction as mp

    for key_attr in (
        "nim_api_key",
        "llm_api_key",
        "gemini_api_key",
        "deepseek_api_key",
        "kimi_api_key",
        "glm_api_key",
    ):
        monkeypatch.setattr(mp.settings, key_attr, "", raising=False)

    response = await catalog_api_client.get(f"/api/v1/markets/{NBA_SLUG}/prediction")

    assert response.status_code == 200
    assert response.json().get("ensemble") is None


@pytest.mark.asyncio
async def test_ensemble_attached_when_providers_answer(catalog_api_client, monkeypatch):
    """When the ensemble returns an aggregate, the API exposes prob/stdev/
    n_models/per-model rationales alongside the XGBoost judge probability."""
    import app.api.v1.market_prediction as mp

    async def _fake_forecast(question, context, settings, *, market_category=None):
        return {
            "prob": 0.62,
            "stdev": 0.08,
            "n_models": 3,
            "spread_flag": False,
            "per_model": [
                {"provider": "primary:openai", "prob": 0.6, "rationale": "r1"},
                {"provider": "deepseek", "prob": 0.55, "rationale": "r2"},
                {"provider": "kimi", "prob": 0.71, "rationale": "r3"},
            ],
        }

    monkeypatch.setattr(mp, "ensemble_forecast", _fake_forecast)
    monkeypatch.setattr(mp.settings, "ensemble_enabled", True)

    response = await catalog_api_client.get(f"/api/v1/markets/{NBA_SLUG}/prediction")

    assert response.status_code == 200
    payload = response.json()
    ens = payload["ensemble"]
    assert ens is not None
    assert ens["n_models"] == 3
    assert ens["prob"] == pytest.approx(0.62)
    assert len(ens["per_model"]) == 3
    # XGBoost judge probability is still a SEPARATE field, untouched.
    assert "predicted_prob" in payload


@pytest.mark.asyncio
async def test_provisional_markets_have_no_edge(catalog_api_client):
    for slug in sorted(CATALOG_SLUGS):
        response = await catalog_api_client.get(f"/api/v1/markets/{slug}/prediction")
        assert response.status_code == 200
        payload = response.json()
        if payload["provisional"]:
            assert payload["is_edge"] is False
