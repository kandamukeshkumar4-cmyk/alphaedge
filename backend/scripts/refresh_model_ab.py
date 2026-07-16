"""Explicit operator refresh for the cached V40 forecast-score A/B readout.

Run from ``backend/`` only after a Railway deployment/config-history reference
has been supplied via the non-secret A/B settings. This script never changes
the deployed model default or submits orders.
"""

from __future__ import annotations

import asyncio
import json

from app.db.session import AsyncSessionLocal
from app.ml.ab_harness import refresh_controlled_ab_readout


async def main() -> None:
    async with AsyncSessionLocal() as session:
        result = await refresh_controlled_ab_readout(session)
        await session.commit()
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":  # pragma: no cover - operator entry point
    asyncio.run(main())
