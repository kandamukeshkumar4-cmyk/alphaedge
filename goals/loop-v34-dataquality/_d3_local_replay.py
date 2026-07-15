"""D3 local ingest replay: measure before/after data-quality counts.

Simulates the four D1 issue classes with fixtures (no network, no prod writes).
Runs hygiene/ingest paths and prints honest before/after counts.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Ensure backend package is importable when run from goals/
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.data_quality.hygiene import (  # noqa: E402
    canonical_kalshi_market_id,
    fold_display_title,
    rekey_orphan_signal_market_ids,
)
from app.db.models import Market, MarketStatus, SignalEvent  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services.live_market_ingest import (  # noqa: E402
    LiveMarketIngestService,
    categorize,
    display_title_for_payload,
)
from app.services.weather_desk import weather_scan_to_events  # noqa: E402
from app.workers.price_feed_worker import lapse_expired_markets  # noqa: E402
from app.workers.tasks import run_weather_scan  # noqa: E402


def _before_logic() -> dict:
    """Pure-logic before/after without DB — mirrors D1 findings + repair rules."""
    # 1) title dups
    raw_titles = ["Kylian Mbappé: 1+ goals", "Kylian Mbappé: 1+ goals"]
    events = ["France vs Morocco", "France vs Spain"]
    folded = [fold_display_title(t, e) for t, e in zip(raw_titles, events)]
    # 2) category
    cat_before_rule = "Sports"  # old keyword order for Trump WC
    cat_after, _ = categorize("President Trump to Attend World Cup Final?", None)
    fifa_after, _ = categorize("Will Egypt win the 2026 FIFA World Cup?", None)
    # 3) weather market_id
    raw_ticker = "KXHIGHMIA-26JUL16-B96.5"
    return {
        "title_dup_groups_before": 1 if len(set(raw_titles)) == 1 else 0,
        "title_dup_groups_after_fold": 1 if len(set(folded)) == 1 else 0,
        "folded_titles": folded,
        "trump_wc_category_before": cat_before_rule,
        "trump_wc_category_after": cat_after,
        "egypt_wc_category_after": fifa_after,
        "weather_market_id_before": raw_ticker,
        "weather_market_id_after": canonical_kalshi_market_id(raw_ticker),
        "weather_events_sample": weather_scan_to_events(
            [
                {
                    "city": "Miami",
                    "buckets": [
                        {
                            "ticker": raw_ticker,
                            "edge": 0.2,
                            "model_probability": 0.4,
                            "market_yes": 0.2,
                            "read": "model rich",
                            "bucket": "96.5 or below",
                        }
                    ],
                }
            ]
        ),
    }


async def _db_replay() -> dict:
    """Optional DB-backed replay when AsyncSessionLocal is available."""
    async with AsyncSessionLocal() as session:
        now = datetime.now(UTC)
        # Seed one stale open market
        stale = Market(
            slug="ks-replay-stale",
            title="Replay stale",
            question="stale?",
            category="Sports",
            icon="🏟️",
            volume=1,
            traders=0,
            market_count=1,
            description="",
            resolution="",
            status=MarketStatus.OPEN,
            lock_at=now - timedelta(days=2),
            source="kalshi",
            external_slug="KXREPLAY-STALE",
        )
        session.add(stale)
        # Seed orphan signal with raw ticker
        session.add(
            SignalEvent(
                signal_type="delta:weather_edge",
                platform="kalshi",
                market_id="KXHIGHMIA-26JUL16-B96.5",
                headline_eligible=True,
                payload={"city": "Miami"},
            )
        )
        await session.flush()

        open_before = (
            await session.execute(
                select(Market).where(
                    Market.slug == "ks-replay-stale",
                    Market.status == MarketStatus.OPEN,
                )
            )
        ).scalar_one_or_none()
        orphan_before = (
            await session.execute(
                select(SignalEvent).where(
                    SignalEvent.market_id == "KXHIGHMIA-26JUL16-B96.5"
                )
            )
        ).scalar_one_or_none()

        lapsed = await lapse_expired_markets(session)
        rekey = await rekey_orphan_signal_market_ids(session, limit=50)
        await session.commit()

        await session.refresh(stale)
        row = (
            await session.execute(
                select(SignalEvent).where(
                    SignalEvent.market_id == "ks-kxhighmia-26jul16-b96.5"
                )
            )
        ).scalar_one_or_none()

        # cleanup
        await session.delete(stale)
        if row is not None:
            await session.delete(row)
        leftover = (
            await session.execute(
                select(SignalEvent).where(
                    SignalEvent.market_id.in_(
                        ["KXHIGHMIA-26JUL16-B96.5", "ks-kxhighmia-26jul16-b96.5"]
                    )
                )
            )
        ).scalars().all()
        for r in leftover:
            await session.delete(r)
        await session.commit()

        return {
            "stale_open_before": 1 if open_before else 0,
            "stale_open_after_lapse": 0 if stale.status == MarketStatus.LOCKED else 1,
            "lapsed": lapsed,
            "orphan_raw_before": 1 if orphan_before else 0,
            "orphan_raw_after_rekey": 0 if row is not None else 1,
            "rekey": rekey,
        }


def main() -> None:
    logic = _before_logic()
    print("=== D3 pure-logic before/after ===")
    print(json.dumps(logic, indent=2, default=str))
    try:
        db = asyncio.run(_db_replay())
        print("=== D3 DB replay before/after ===")
        print(json.dumps(db, indent=2, default=str))
    except Exception as exc:  # noqa: BLE001
        print("=== D3 DB replay skipped ===")
        print(str(exc))


if __name__ == "__main__":
    main()
