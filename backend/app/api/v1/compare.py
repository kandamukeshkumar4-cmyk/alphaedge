"""O03 — Market comparison (Loop V10).

``GET /api/v1/compare?slugs=a,b[,c,d]`` — side-by-side compact intelligence for
2-4 markets. Each entry reuses the M02 share-snapshot core builder
(``{found, slug, title, yes_price, edge, top_signal, arb_matched,
smart_money_note}``), so the compare columns and the share card never disagree.

**PUBLIC GET.** Read-only composition — no new table, persists nothing, order
path never imported. Robust parsing: comma-separated ``slugs``; >4 slugs are
clamped to the first 4; a bad/unknown slug degrades to ``{found:false}`` for
THAT entry only (never a 404, never fabricated). No slugs → honest empty
``{entries: [], count: 0}``. Swept by the I01 5xx guard.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.market_snapshot import build_share_snapshot_core
from app.core.config import get_settings
from app.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["compare"])
settings = get_settings()

# Side-by-side compare is meaningful for a small handful of markets; a public GET
# must never do unbounded work, so extra slugs are clamped away.
_MAX_SLUGS = 4

COMPARE_DISCLAIMER = (
    "Market comparison — side-by-side compact intelligence (price, model edge, "
    "top signal, arb and smart-money) reusing the shareable snapshot builder. "
    "Signal only; paper trading only — simulated funds, no execution."
)


def _parse_slugs(raw: str | None) -> tuple[list[str], bool]:
    """(unique slugs clamped to the first ``_MAX_SLUGS``, clamped?) from a
    comma-separated string. Blanks and duplicates are dropped, order preserved."""
    if not raw:
        return [], False
    seen: set[str] = set()
    parsed: list[str] = []
    for part in raw.split(","):
        s = part.strip()
        if not s or s in seen:
            continue
        seen.add(s)
        parsed.append(s)
    clamped = len(parsed) > _MAX_SLUGS
    return parsed[:_MAX_SLUGS], clamped


@router.get("/compare")
async def compare_markets(
    slugs: str | None = Query(
        default=None, description="Comma-separated market slugs (2-4)"
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    parsed, clamped = _parse_slugs(slugs)

    entries: list[dict[str, Any]] = []
    for slug in parsed:
        entries.append(await build_share_snapshot_core(db, slug))

    return {
        "entries": entries,
        "count": len(entries),
        "requested": parsed,
        "clamped": clamped,
        "max_slugs": _MAX_SLUGS,
        "paper_trading_only": settings.paper_trading_only,
        "signal_only": True,
        "disclaimer": COMPARE_DISCLAIMER,
        "generated_at": datetime.now(UTC).isoformat(),
    }
