"""Exa news connector tests."""

import pytest


@pytest.mark.asyncio
async def test_exa_news_brief_parses_results(monkeypatch):
    """Exa search results -> NewsSignal with tone-derived sentiment."""
    from app.signals import news_fetcher

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [
                {"title": "Argentina wins epic match", "highlights": ["a strong surge"]},
                {"title": "Cape Verde crash out after loss", "highlights": []},
                {"title": "Neutral preview", "highlights": []},
            ]}

    class FakeClient:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None, headers=None):
            assert headers["x-api-key"] == "test-key"
            assert json["category"] == "news"
            return FakeResponse()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: type("S", (), {"exa_api_key": "test-key"})(),
    )
    signal = await news_fetcher.exa_news_brief("world cup argentina")
    assert signal is not None
    assert signal.sources_count == 3
    assert -1.0 <= signal.sentiment_score <= 1.0
    assert signal.headline == "Argentina wins epic match"


@pytest.mark.asyncio
async def test_exa_news_brief_none_without_key(monkeypatch):
    from app.signals import news_fetcher

    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: type("S", (), {"exa_api_key": ""})(),
    )
    assert await news_fetcher.exa_news_brief("anything") is None
