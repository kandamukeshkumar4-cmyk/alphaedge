"""Loop V46 K1 evidence harness — quantify every kalshi_open_events skip reason.

Mirrors goals/loop-v33-lockbreadth/evidence/local_funnel_run.py but instruments
the filter path in kalshi_live_ingest.sync_open_events so we can see WHY
V33 observed imported=0 / skipped=200.

Run from ``backend/``:

    cp ../goals/loop-v46-kalshi/evidence/local_kalshi_audit.py ./_run.py
    PAPER_TRADING_ONLY=true LIVE_FEED_ENABLED=true \\
        uv run --extra dev python _run.py && rm _run.py

Hits real upstream Kalshi APIs read-only; writes only to a throwaway SQLite file
and prints a JSON audit report. No order path.
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import sys
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models import Base, Market
from app.services.kalshi_live_ingest import (
    KalshiLiveIngestService,
    _KALSHI_CATEGORY_MAP,
    _map_kalshi_category,
    _volume_usd,
)

DB = pathlib.Path(__file__).resolve().parent / "loop46_kalshi_audit.db"
if DB.exists():
    DB.unlink()
URL = f"sqlite+aiosqlite:///{DB.as_posix()}"


def _audit_filter_path(
    events: list[dict[str, Any]],
    board: list[dict[str, Any]],
    *,
    series: str,
    per_category_limit: int = 6,
    max_markets_per_event: int = 6,
) -> dict[str, Any]:
    """Replicate sync_open_events filter branches with per-reason counters.

    Source of truth for branch order:
      backend/app/services/kalshi_live_ingest.py:sync_open_events (L60-L133)
    """
    markets_by_event: dict[str, list[dict[str, Any]]] = {}
    for market in board:
        markets_by_event.setdefault(str(market.get("event_ticker") or ""), []).append(market)

    n_categories = len({c for c, _ in _KALSHI_CATEGORY_MAP.values()})
    hard_cap = per_category_limit * n_categories  # L90

    reasons: Counter[str] = Counter()
    picked: dict[str, int] = {}
    would_import_events = 0
    would_import_markets = 0
    category_picked_detail: dict[str, int] = {}
    sample_missing_board: list[str] = []
    sample_would_import: list[dict[str, Any]] = []
    raw_categories: Counter[str] = Counter()
    mapped_categories: Counter[str] = Counter()
    volumes_if_imported: list[int] = []
    event_tickers_seen: list[str] = []
    board_event_keys = set(markets_by_event.keys()) - {""}

    # Case-sensitivity probe (not applied by production path)
    board_upper = {k.upper() for k in board_event_keys}
    case_mismatch_only = 0

    # Mirror production break/continue order exactly
    # (backend/app/services/kalshi_live_ingest.py:89-130)
    i = 0
    while i < len(events):
        if sum(picked.values()) >= hard_cap:
            reasons["hard_cap_break_unexamined"] = len(events) - i
            break
        event = events[i]
        i += 1
        if not isinstance(event, dict):
            reasons["not_dict"] += 1
            continue
        event_ticker = str(event.get("event_ticker") or "")
        if not event_ticker:
            reasons["empty_event_ticker"] += 1
            continue
        event_tickers_seen.append(event_ticker)
        if event_ticker.startswith(series):
            reasons["wc_series_deferred"] += 1
            continue
        raw_category = str(event.get("category") or "")
        raw_categories[raw_category or "<empty>"] += 1
        category, _icon = _map_kalshi_category(raw_category)
        mapped_categories[category] += 1
        if picked.get(category, 0) >= per_category_limit:
            reasons["per_category_limit"] += 1
            continue

        markets = markets_by_event.get(event_ticker)
        if markets is None:
            reasons["no_markets_on_board"] += 1  # L104-L106 — production skipped++
            if len(sample_missing_board) < 12:
                sample_missing_board.append(event_ticker)
            if event_ticker.upper() in board_upper:
                case_mismatch_only += 1
            continue
        markets = markets[:max_markets_per_event]
        if not markets:
            reasons["empty_markets_slice"] += 1  # L108-L110 — production skipped++
            continue

        # Production picks the event then upserts each market with a ticker
        picked[category] = picked.get(category, 0) + 1
        category_picked_detail[category] = picked[category]
        would_import_events += 1
        tickers_ok = 0
        for market in markets:
            if not str(market.get("ticker") or ""):
                reasons["market_missing_ticker"] += 1  # L115-L116 (NOT in skipped)
                continue
            tickers_ok += 1
            would_import_markets += 1
        event_volume = sum(_volume_usd(m) for m in markets)
        volumes_if_imported.append(event_volume)
        if len(sample_would_import) < 10:
            sample_would_import.append(
                {
                    "event_ticker": event_ticker,
                    "title": str(event.get("title") or "")[:80],
                    "raw_category": raw_category,
                    "mapped_category": category,
                    "markets_on_board": len(markets_by_event.get(event_ticker, [])),
                    "markets_capped": len(markets),
                    "event_volume": event_volume,
                    "tickers_ok": tickers_ok,
                }
            )
        reasons["picked_for_import"] += 1

    # Join diagnostics: how many open-event tickers appear on the board at all?
    event_set = {str(e.get("event_ticker") or "") for e in events if isinstance(e, dict)}
    event_set.discard("")
    join_hit = len(event_set & board_event_keys)
    join_miss = len(event_set - board_event_keys)
    board_only = len(board_event_keys - event_set)

    # Volume floor probe (NOT currently applied — measure for K2 honesty)
    zero_vol = sum(1 for v in volumes_if_imported if v <= 0)
    low_vol_1k = sum(1 for v in volumes_if_imported if 0 < v < 1000)

    # Unmapped categories (fall through to Culture via L308)
    unmapped_raw = [
        (cat, n)
        for cat, n in raw_categories.most_common()
        if cat != "<empty>" and cat.strip().lower() not in _KALSHI_CATEGORY_MAP
    ]

    # Production skipped counter = no_markets_on_board + empty_markets_slice only
    production_skipped = reasons["no_markets_on_board"] + reasons["empty_markets_slice"]

    return {
        "n_events_fetched": len(events),
        "n_board_markets": len(board),
        "n_board_event_tickers": len(board_event_keys),
        "n_mapped_category_buckets": n_categories,
        "hard_cap": hard_cap,
        "per_category_limit": per_category_limit,
        "max_markets_per_event": max_markets_per_event,
        "series_prefix_deferred": series,
        "reason_counts": dict(reasons),
        "production_skipped_equivalent": production_skipped,
        "would_import_events": would_import_events,
        "would_import_markets": would_import_markets,
        "category_picked": category_picked_detail,
        "join": {
            "event_tickers_in_list": len(event_set),
            "hit_board": join_hit,
            "miss_board": join_miss,
            "board_only_events_not_in_top200": board_only,
            "case_mismatch_only": case_mismatch_only,
        },
        "raw_categories_top": raw_categories.most_common(20),
        "mapped_categories": dict(mapped_categories),
        "unmapped_raw_categories": unmapped_raw[:20],
        "volume_probe_on_picked": {
            "zero_or_missing": zero_vol,
            "between_1_and_999": low_vol_1k,
            "gte_1000": sum(1 for v in volumes_if_imported if v >= 1000),
            "min": min(volumes_if_imported) if volumes_if_imported else None,
            "max": max(volumes_if_imported) if volumes_if_imported else None,
            "median": (
                sorted(volumes_if_imported)[len(volumes_if_imported) // 2]
                if volumes_if_imported
                else None
            ),
        },
        "sample_missing_board": sample_missing_board,
        "sample_would_import": sample_would_import,
        # Counterfactual: no per-category limit, no hard cap — still join-gated
        "counterfactual_no_caps": _counterfactual_no_caps(
            events, markets_by_event, series=series, max_markets_per_event=max_markets_per_event
        ),
        # Counterfactual: join via per-event fetch for first N miss tickers (expensive)
        # measured separately only if join_miss dominates
    }


def _counterfactual_no_caps(
    events: list[dict[str, Any]],
    markets_by_event: dict[str, list[dict[str, Any]]],
    *,
    series: str,
    max_markets_per_event: int,
) -> dict[str, int]:
    events_ok = 0
    markets_ok = 0
    no_board = 0
    wc = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        et = str(event.get("event_ticker") or "")
        if not et:
            continue
        if et.startswith(series):
            wc += 1
            continue
        markets = markets_by_event.get(et)
        if not markets:
            no_board += 1
            continue
        events_ok += 1
        markets_ok += sum(
            1 for m in markets[:max_markets_per_event] if str(m.get("ticker") or "")
        )
    return {
        "wc_deferred": wc,
        "no_markets_on_board": no_board,
        "events_importable": events_ok,
        "markets_importable": markets_ok,
    }


async def main() -> None:
    settings = get_settings()
    report: dict[str, Any] = {
        "ts": datetime.now(UTC).isoformat(),
        "paper_trading_only": settings.paper_trading_only,
        "kalshi_api_base_url": settings.kalshi_api_base_url,
        "live_kalshi_series": settings.live_kalshi_series,
        "code_refs": {
            "sync_open_events": "backend/app/services/kalshi_live_ingest.py:60-133",
            "list_open_events": "backend/app/data/connectors/kalshi.py:39-48",
            "list_open_markets": "backend/app/data/connectors/kalshi.py:68-93",
            "category_map": "backend/app/services/kalshi_live_ingest.py:287-308",
            "per_category_limit_default": "backend/app/services/kalshi_live_ingest.py:63",
            "max_markets_per_event_default": "backend/app/services/kalshi_live_ingest.py:64",
            "hard_cap_break": "backend/app/services/kalshi_live_ingest.py:90-91",
            "wc_series_skip": "backend/app/services/kalshi_live_ingest.py:95-96",
            "category_bucket_continue": "backend/app/services/kalshi_live_ingest.py:99-100",
            "skipped_no_markets": "backend/app/services/kalshi_live_ingest.py:104-110",
            "skipped_counter_return": "backend/app/services/kalshi_live_ingest.py:133",
            "note": (
                "Production `skipped` ONLY increments on missing/empty board join "
                "(L104-110). Category caps and WC deferral use bare `continue` and "
                "are invisible in the returned skipped count."
            ),
        },
    }

    engine = create_async_engine(URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        service = KalshiLiveIngestService(session)
        # Fetch raw upstream once for instrumentation (same calls as production)
        try:
            events = await asyncio.to_thread(service._fetcher.list_open_events, limit=200)
            report["fetch_events"] = {"ok": True, "count": len(events)}
        except Exception as e:
            report["fetch_events"] = {
                "ok": False,
                "error": f"{type(e).__name__}: {str(e)[:200]}",
            }
            print(json.dumps(report, indent=2, default=str))
            await engine.dispose()
            return

        try:
            board = await asyncio.to_thread(service._fetcher.list_open_markets)
            report["fetch_board"] = {"ok": True, "count": len(board)}
        except Exception as e:
            report["fetch_board"] = {
                "ok": False,
                "error": f"{type(e).__name__}: {str(e)[:200]}",
            }
            print(json.dumps(report, indent=2, default=str))
            await engine.dispose()
            return

        report["filter_audit"] = _audit_filter_path(
            events,
            board,
            series=settings.live_kalshi_series,
            per_category_limit=6,
            max_markets_per_event=6,
        )

        # Real service call (production path) for before-counts
        try:
            summary = await service.sync_open_events()
            await session.commit()
            report["production_sync_open_events"] = summary
        except Exception as e:
            report["production_sync_open_events"] = (
                f"ERR {type(e).__name__}: {str(e)[:200]}"
            )

        # Catalog count after
        from sqlalchemy import func, select

        kalshi_count = await session.scalar(
            select(func.count()).select_from(Market).where(Market.source == "kalshi")
        )
        report["catalog_kalshi_markets_after"] = kalshi_count

    # Spot-check: for a few join-miss tickers, call list_event_markets to see if
    # markets exist under per-event fetch (diagnoses board pagination / join bugs).
    misses = report["filter_audit"]["sample_missing_board"][:5]
    if misses:
        connector = KalshiLiveIngestService.__new__(KalshiLiveIngestService)
        # Use a fresh connector via settings
        from app.data.connectors.kalshi import KalshiConnector

        conn = KalshiConnector(base_url=settings.kalshi_api_base_url)
        per_event: dict[str, Any] = {}
        for et in misses:
            try:
                ms = await asyncio.to_thread(conn.list_event_markets, et)
                per_event[et] = {
                    "count": len(ms),
                    "sample_tickers": [str(m.get("ticker") or "") for m in ms[:3]],
                    "sample_statuses": [str(m.get("status") or "") for m in ms[:3]],
                }
            except Exception as e:
                per_event[et] = f"ERR {type(e).__name__}: {str(e)[:120]}"
        report["per_event_fetch_probe_on_join_misses"] = per_event

    out_path = pathlib.Path(__file__).resolve().parent / "k1_audit_report.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    print(f"\n# wrote {out_path}", file=sys.stderr)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
