from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.data.snapshots import OddsSnapshotRecord


@dataclass(frozen=True)
class NormalizedMarketSnapshot:
    market_slug: str
    implied_yes: float
    source: str
    captured_at: datetime
    book: str | None = None
    event_id: str | None = None
    platform_market_id: str | None = None
    title: str | None = None
    market_type: str = "binary"
    outcome_name: str = "Yes"
    line: Decimal | None = None
    close_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_odds_snapshot_record(self) -> OddsSnapshotRecord:
        return OddsSnapshotRecord(
            market_slug=self.market_slug,
            implied_yes=self.implied_yes,
            source=self.source,
            captured_at=self.captured_at,
            book=self.book,
            event_id=self.event_id,
            platform_market_id=self.platform_market_id,
            title=self.title,
            market_type=self.market_type,
            outcome_name=self.outcome_name,
            line=self.line,
            price=self.implied_yes,
            close_at=self.close_at,
            metadata=self.metadata,
        )


def parse_timestamp(value: datetime | str | None, fallback: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    elif fallback is not None:
        parsed = fallback
    else:
        parsed = datetime.now(UTC)

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def probability_from_decimalish(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        probability = float(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return None
    if 0.0 <= probability <= 1.0:
        return round(probability, 4)
    if 1.0 < probability <= 100.0:
        return round(probability / 100.0, 4)
    return None


def probability_from_american_odds(value: object) -> float | None:
    try:
        odds = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if odds == 0:
        return None
    if odds > 0:
        probability = Decimal("100") / (odds + Decimal("100"))
    else:
        probability = abs(odds) / (abs(odds) + Decimal("100"))
    return float(probability)


def decode_jsonish(value: object) -> object:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def slugify(value: object) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "unknown"
