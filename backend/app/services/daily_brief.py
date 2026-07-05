"""Daily brief assembly + channel formatters (T14).

Attribution: the daily-dashboard → channel-push shape is adapted from the
MIT-licensed ZhuLinsen/daily_stock_analysis project. NONE of its stock
technical-analysis strategies are used and there is NO order-placing path — this is
pure assembly from existing tables (prices, model forecast, signal events, graded
claims) into a research brief. LLM output is a brief only, never a trade trigger.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_COMPACT_MAX = 4000


@dataclass(frozen=True)
class MarketLine:
    slug: str
    price: float | None
    model_prob: float | None
    edge: float | None
    is_edge: bool
    news_driver: str | None
    whale_line: str | None


@dataclass
class DailyBrief:
    date_str: str
    market_lines: list[MarketLine] = field(default_factory=list)
    new_briefs: int = 0
    claims_correct: int = 0
    claims_incorrect: int = 0


async def _latest_price(session: AsyncSession, slug: str) -> float | None:
    from app.db.models import OddsSnapshot

    row = await session.scalar(
        select(OddsSnapshot.implied_yes)
        .where(OddsSnapshot.market_slug == slug)
        .order_by(OddsSnapshot.captured_at.desc())
        .limit(1)
    )
    return float(row) if row is not None else None


async def _latest_signal_line(session: AsyncSession, slug: str, signal_type: str) -> str | None:
    from app.db.models import SignalEvent

    row = await session.scalar(
        select(SignalEvent.payload)
        .where(SignalEvent.market_id == slug, SignalEvent.signal_type == signal_type)
        .order_by(SignalEvent.created_at.desc())
        .limit(1)
    )
    if not isinstance(row, dict):
        return None
    direction = row.get("direction", "")
    detail = row.get("detail", {}) if isinstance(row.get("detail"), dict) else {}
    return f"{direction} {detail}".strip() or None


async def assemble_daily_brief(
    session: AsyncSession, *, now: datetime, slugs: list[str]
) -> DailyBrief:
    """Pure assembly from existing tables — no new analysis, deterministic per input."""
    from app.db.models import AnalystBrief, BriefClaim
    from app.forecasting.predictor import predict_market

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    lines: list[MarketLine] = []
    for slug in slugs:
        price = await _latest_price(session, slug)
        model_prob = edge = None
        is_edge = False
        if price is not None:
            try:
                pred = predict_market({"implied_yes": price, "market_slug": slug})
                model_prob = pred.predicted_prob
                edge = pred.edge
                is_edge = pred.is_edge
            except Exception:  # noqa: BLE001 - forecast is best-effort, never blocks the brief
                logger.debug("predict_market failed in daily brief for %s", slug, exc_info=True)
        news = await _latest_signal_line(session, slug, "delta:news_arrival")
        whale = await _latest_signal_line(session, slug, "delta:whale_delta")
        lines.append(
            MarketLine(
                slug=slug, price=price, model_prob=model_prob, edge=edge,
                is_edge=is_edge, news_driver=news, whale_line=whale,
            )
        )

    new_briefs = await session.scalar(
        select(func.count()).select_from(AnalystBrief).where(
            AnalystBrief.kind == "brief", AnalystBrief.created_at >= day_start
        )
    )
    correct = await session.scalar(
        select(func.count()).select_from(BriefClaim).where(
            BriefClaim.status == "correct", BriefClaim.resolved_at >= day_start
        )
    )
    incorrect = await session.scalar(
        select(func.count()).select_from(BriefClaim).where(
            BriefClaim.status == "incorrect", BriefClaim.resolved_at >= day_start
        )
    )
    return DailyBrief(
        date_str=now.strftime("%Y-%m-%d"),
        market_lines=lines,
        new_briefs=int(new_briefs or 0),
        claims_correct=int(correct or 0),
        claims_incorrect=int(incorrect or 0),
    )


def _market_line_text(line: MarketLine) -> str:
    price = f"{line.price:.0%}" if line.price is not None else "n/a"
    model = f"{line.model_prob:.0%}" if line.model_prob is not None else "n/a"
    edge = f"{line.edge:+.1%}" if line.edge is not None else "n/a"
    gate = "EDGE" if line.is_edge else "no-edge"
    extras = []
    if line.news_driver:
        extras.append(f"news:{line.news_driver}")
    if line.whale_line:
        extras.append(f"whale:{line.whale_line}")
    tail = (" · " + " · ".join(extras)) if extras else ""
    return f"{line.slug}: price {price}, model {model}, edge {edge} ({gate}){tail}"


def daily_brief_markdown(brief: DailyBrief) -> str:
    """Full markdown for web / WS surfaces."""
    header = (
        f"# Daily Brief {brief.date_str}\n\n"
        f"**Claim scoreboard (today):** {brief.claims_correct} correct / "
        f"{brief.claims_incorrect} incorrect · **{brief.new_briefs} new briefs**\n\n"
    )
    if not brief.market_lines:
        return header + "_No tracked markets moved today._\n"
    body = "\n".join(f"- {_market_line_text(line)}" for line in brief.market_lines)
    return header + body + "\n"


def daily_brief_compact(brief: DailyBrief, *, max_chars: int = _COMPACT_MAX) -> str:
    """Telegram/Discord-safe compact form, hard-capped at max_chars."""
    head = (
        f"📊 Daily Brief {brief.date_str} — "
        f"{brief.claims_correct}-{brief.claims_incorrect} claims, "
        f"{brief.new_briefs} briefs"
    )
    lines = [head]
    for line in brief.market_lines:
        candidate = "\n".join(lines + [_market_line_text(line)])
        if len(candidate) > max_chars:
            lines.append("…")
            break
        lines.append(_market_line_text(line))
    return "\n".join(lines)[:max_chars]
