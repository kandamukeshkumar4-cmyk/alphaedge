from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Market, MarketStatus, OddsSnapshot, OrderOutcome
from app.ml.features import FEATURE_COLUMNS, build_feature_matrix_from_frames


async def load_resolved_snapshot_feature_matrix(session: AsyncSession) -> pd.DataFrame:
    result = await session.execute(
        select(OddsSnapshot, Market)
        .join(Market, Market.slug == OddsSnapshot.market_slug)
        .where(
            Market.status == MarketStatus.RESOLVED,
            Market.winning_outcome.is_not(None),
        )
        .order_by(OddsSnapshot.market_slug, OddsSnapshot.captured_at)
    )
    rows = result.all()
    if not rows:
        return pd.DataFrame(columns=["market_slug", *FEATURE_COLUMNS, "label"])

    odds_rows: list[dict[str, Any]] = []
    score_rows: dict[str, dict[str, int | str]] = {}
    for snapshot, market in rows:
        metadata = snapshot.snapshot_metadata or {}
        odds_row: dict[str, Any] = {
            "market_slug": snapshot.market_slug,
            "captured_at": snapshot.captured_at,
            "implied_yes": float(snapshot.implied_yes),
            "source": snapshot.source,
            "close_at": snapshot.close_at or market.lock_at,
            "book": snapshot.book,
            "event_id": snapshot.event_id,
            "platform_market_id": snapshot.platform_market_id,
            "title": snapshot.title,
            "market_type": snapshot.market_type,
            "outcome_name": snapshot.outcome_name,
            "price": float(snapshot.price) if snapshot.price is not None else None,
        }
        for field in (
            "implied_no",
            "executable_yes_ask",
            "executable_no_ask",
            "yes_bid",
            "no_bid",
        ):
            if field in metadata:
                odds_row[field] = metadata[field]
        odds_rows.append(odds_row)

        score_rows[market.slug] = {
            "market_slug": market.slug,
            "winner_yes": 1 if market.winning_outcome == OrderOutcome.YES else 0,
        }

    return build_feature_matrix_from_frames(
        pd.DataFrame(odds_rows),
        pd.DataFrame(score_rows.values()),
    )
