"""H1 — wall-clock seconds until next 06:00 UTC for morning research loop."""
from __future__ import annotations

from datetime import datetime, timezone

from app.main import _seconds_until_next_utc_hour


def test_seconds_until_next_utc_hour_before_target():
    now = datetime(2026, 7, 21, 5, 0, 0, tzinfo=timezone.utc)
    assert _seconds_until_next_utc_hour(now, hour=6) == 3600.0


def test_seconds_until_next_utc_hour_just_after_target():
    now = datetime(2026, 7, 21, 6, 0, 1, tzinfo=timezone.utc)
    assert _seconds_until_next_utc_hour(now, hour=6) == 86399.0


def test_seconds_until_next_utc_hour_afternoon():
    now = datetime(2026, 7, 21, 18, 0, 0, tzinfo=timezone.utc)
    assert _seconds_until_next_utc_hour(now, hour=6) == 43200.0
