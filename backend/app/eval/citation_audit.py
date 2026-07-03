"""Citation-faithfulness audit (T08): structural, no LLM.

Confirms a brief did not cite evidence that only existed AFTER it was written
(post-hoc citation). News/wallet citations must map to a signal_event of the right
kind for that market with created_at < brief.created_at. Model/orderbook citations
are computed at brief time and are inherently faithful.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class CitationAuditResult:
    total: int
    faithful: int
    suspect: int

    @property
    def ok(self) -> bool:
        return self.suspect == 0


_KIND_TO_SIGNAL = {
    "news": "delta:news_arrival",
    "wallet": "delta:whale_delta",
}


async def audit_brief_citations(session: AsyncSession, brief) -> CitationAuditResult:
    """Audit one AnalystBrief row's citations for post-hoc evidence."""
    from app.db.models import SignalEvent

    citations = brief.citations or []
    total = len(citations)
    faithful = 0
    suspect = 0

    for citation in citations:
        kind = str(citation.get("kind", ""))
        signal_type = _KIND_TO_SIGNAL.get(kind)
        if signal_type is None:
            # model / orderbook: computed at brief time -> faithful by construction
            faithful += 1
            continue
        count = await session.scalar(
            select(func.count())
            .select_from(SignalEvent)
            .where(
                SignalEvent.market_id == brief.market_slug,
                SignalEvent.signal_type == signal_type,
                SignalEvent.created_at < brief.created_at,
            )
        )
        if count and count > 0:
            faithful += 1
        else:
            suspect += 1  # cited evidence that did not exist before the brief

    return CitationAuditResult(total=total, faithful=faithful, suspect=suspect)
