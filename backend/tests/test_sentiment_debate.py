"""Loop V61 S3 flag/provenance/no-probability tests."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.signals.news_cadence import NewsRefreshCandidate
from app.signals.sentiment_debate import (
    LENSES,
    _get_nim_client,
    persist_debate,
    reset_nim_client,
    run_news_debate,
)

class _Completions:
    async def create(self, **kwargs):
        assert "probability" in kwargs["messages"][0]["content"]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"verdict":"supported","rationale":"headline evidence","cited_inputs":["public headline"]}'))])


class _Client:
    chat = SimpleNamespace(completions=_Completions())


def _settings(**changes):
    values = {"sentiment_debate_enabled": True, "nim_api_key": "key", "nim_base_url": "https://nim", "nemotron_model": "nim-test", "sentiment_debate_timeout": 1}
    values.update(changes)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_debate_runs_three_lenses_and_persists_provenance(db_session):
    candidate = NewsRefreshCandidate("m1", None, 0.1, 0.7)
    verdicts = await run_news_debate(candidate=candidate, title="Market", headline="Public news", sentiment_score=0.5, settings=_settings(), client=_Client(), now=datetime(2026, 7, 17, tzinfo=UTC))
    assert [verdict.lens for verdict in verdicts] == list(LENSES)
    assert all(verdict.model_id == "nim-test" for verdict in verdicts)
    persist_debate(db_session, market_slug="m1", verdicts=verdicts)
    await db_session.flush()
    from sqlalchemy import select
    from app.db.models import AnalystBrief
    rows = (await db_session.execute(select(AnalystBrief).where(AnalystBrief.market_slug == "m1"))).scalars().all()
    assert len(rows) == 3
    assert all(
        row.kind == "debate"
        and row.tools_used[0]["lens"] in LENSES
        and row.tools_used[0]["verdict"] == "supported"
        for row in rows
    )


@pytest.mark.asyncio
async def test_debate_is_honestly_unavailable_when_flag_or_key_is_missing():
    candidate = NewsRefreshCandidate("m1", None, 0.1, 0.7)
    now = datetime(2026, 7, 17, tzinfo=UTC)
    assert await run_news_debate(candidate=candidate, title="Market", headline="Public news", sentiment_score=0.5, settings=_settings(sentiment_debate_enabled=False), now=now) == []
    assert await run_news_debate(candidate=candidate, title="Market", headline="Public news", sentiment_score=0.5, settings=_settings(nim_api_key=""), now=now) == []
    cold = NewsRefreshCandidate("cold", None, 0.0, 0.0)
    assert await run_news_debate(candidate=cold, title="Market", headline="Public news", sentiment_score=0.5, settings=_settings(), client=_Client(), now=now) == []


def test_module_level_nim_client_is_reused():
    """Loop V70: no per-call AsyncOpenAI construction leak."""
    reset_nim_client()
    settings = _settings(nim_base_url="https://nim.example/v1", nim_api_key="k1")
    fake = MagicMock(name="AsyncOpenAI")
    with patch("openai.AsyncOpenAI", return_value=fake) as ctor:
        a = _get_nim_client(settings)
        b = _get_nim_client(settings)
        assert a is b is fake
        assert ctor.call_count == 1
        # Credential change rebuilds once.
        c = _get_nim_client(_settings(nim_base_url="https://nim.example/v1", nim_api_key="k2"))
        assert c is fake
        assert ctor.call_count == 2
    reset_nim_client()
