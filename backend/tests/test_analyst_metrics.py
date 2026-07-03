"""T08 — analyst metrics aggregation + provisional flag + citation audit."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.eval.analyst_metrics import ClaimRecord, aggregate_claims

NOW = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)


def _rec(status, *, conf=0.7, direction="up", category="Politics", days_ago=1,
         mv="lgbm-1", pv="v1"):
    return ClaimRecord(
        resolved_at=NOW - timedelta(days=days_ago),
        status=status,
        confidence=conf,
        direction=direction,
        category=category,
        model_version=mv,
        prompt_version=pv,
    )


def test_overall_accuracy_and_provisional():
    records = [_rec("correct")] * 6 + [_rec("incorrect")] * 4  # 10 claims, 60% acc
    aggs = aggregate_claims(records, now=NOW)
    overall = [a for a in aggs if a.dimension == "overall" and a.window_days == 0][0]
    assert overall.n == 10
    assert overall.accuracy == 0.6
    assert overall.provisional is True  # n < 30


def test_not_provisional_at_30():
    records = [_rec("correct")] * 30
    overall = [
        a for a in aggregate_claims(records, now=NOW)
        if a.dimension == "overall" and a.window_days == 0
    ][0]
    assert overall.n == 30
    assert overall.provisional is False


def test_void_and_pending_excluded():
    records = [_rec("correct"), _rec("void"), _rec("pending")]
    overall = [
        a for a in aggregate_claims(records, now=NOW)
        if a.dimension == "overall" and a.window_days == 0
    ][0]
    assert overall.n == 1  # only the resolved correct/incorrect count


def test_rolling_windows_filter_by_resolved_at():
    records = [_rec("correct", days_ago=1), _rec("incorrect", days_ago=20)]
    aggs = aggregate_claims(records, now=NOW)
    w7 = [a for a in aggs if a.dimension == "overall" and a.window_days == 7][0]
    w30 = [a for a in aggs if a.dimension == "overall" and a.window_days == 30][0]
    assert w7.n == 1  # only the 1-day-ago claim
    assert w30.n == 2


def test_brier_rewards_calibrated_confidence():
    # a correct claim with high confidence has low Brier
    high = aggregate_claims([_rec("correct", conf=0.9)] * 5, now=NOW)
    low = aggregate_claims([_rec("correct", conf=0.5)] * 5, now=NOW)
    hb = [a for a in high if a.dimension == "overall" and a.window_days == 0][0].brier
    lb = [a for a in low if a.dimension == "overall" and a.window_days == 0][0].brier
    assert hb < lb  # 0.9 closer to outcome 1.0 than 0.5


def test_dimensions_split_by_category_and_claim_type():
    records = [_rec("correct", category="Politics"), _rec("incorrect", category="Crypto")]
    aggs = aggregate_claims(records, now=NOW)
    cats = {a.dim_key for a in aggs if a.dimension == "category"}
    assert cats == {"Politics", "Crypto"}


# --- citation audit -------------------------------------------------------


@pytest.mark.asyncio
async def test_citation_audit_flags_posthoc_news(db_session):
    from app.db.models import AnalystBrief, SignalEvent
    from app.eval.citation_audit import audit_brief_citations

    t0 = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
    slug = "pm-audit"
    # a news signal that existed BEFORE the brief
    db_session.add(
        SignalEvent(
            id=uuid4(), signal_type="delta:news_arrival", platform="news",
            market_id=slug, payload={}, created_at=t0 - timedelta(minutes=5),
        )
    )
    await db_session.flush()

    faithful_brief = AnalystBrief(
        id=uuid4(), market_slug=slug, headline="h", body_markdown="b",
        citations=[{"kind": "model", "ref": "m"}, {"kind": "news", "ref": "n"}],
        created_at=t0,
    )
    posthoc_brief = AnalystBrief(
        id=uuid4(), market_slug="pm-other", headline="h", body_markdown="b",
        citations=[{"kind": "news", "ref": "n"}],  # no prior news signal for pm-other
        created_at=t0,
    )
    db_session.add_all([faithful_brief, posthoc_brief])
    await db_session.flush()

    ok = await audit_brief_citations(db_session, faithful_brief)
    assert ok.suspect == 0 and ok.faithful == 2 and ok.ok is True

    bad = await audit_brief_citations(db_session, posthoc_brief)
    assert bad.suspect == 1 and bad.ok is False
