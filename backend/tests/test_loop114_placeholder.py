"""Loop114 — year-boundary whole-hour placeholder lock detection.

VERIFY112: prod Israel-PM locks are Dec-31 00:00 and Jan-1 15:00. The
loop112 detector only treated Jan-1 00:00:00 and Dec-31 23:59 as
placeholders, so real pairs scored confidence 0 via resolution_date_reject.

Widened rule (minimal): Dec 30–Jan 2 AND whole hour (minute==0, second==0).
No other matcher thresholds changed. Paper SIM only.
"""
from __future__ import annotations

from datetime import UTC, datetime

from app.signals.matching import _is_placeholder_end, match_venue_markets

# Titles from VERIFY112 / MATCHER-DIAG112 pair set A.
A1_PM = "Will Itamar Ben Gvir be the next Prime Minister of Israel?"
A1_KS = "Who will succeed Netanyahu as Prime Minister of Israel?: Itamar Ben-Gvir"

# REAL prod timestamps from VERIFY112 (not the idealized 23:59 / 00:00 fixtures).
PROD_PM_LOCK = datetime(2026, 12, 31, 0, 0, 0, tzinfo=UTC)
PROD_KS_LOCK = datetime(2045, 1, 1, 15, 0, 0, tzinfo=UTC)

PERSIST_FLOOR = 0.50


def test_year_boundary_whole_hour_locks_are_placeholder():
    """The two real prod shapes from VERIFY112 must be placeholder-shaped."""
    assert _is_placeholder_end(PROD_PM_LOCK)
    assert _is_placeholder_end(PROD_KS_LOCK)
    # Adjacent whole-hour year-boundary forms also qualify.
    assert _is_placeholder_end(datetime(2026, 12, 30, 0, 0, 0, tzinfo=UTC))
    assert _is_placeholder_end(datetime(2045, 1, 2, 12, 0, 0, tzinfo=UTC))


def test_midseason_game_locks_stay_sharp():
    """An MLB-style July date must NOT become a placeholder."""
    assert not _is_placeholder_end(datetime(2026, 7, 18, 18, 0, 0, tzinfo=UTC))
    assert not _is_placeholder_end(datetime(2026, 7, 18, 0, 0, 0, tzinfo=UTC))
    # Non-whole-hour on the year boundary stays sharp.
    assert not _is_placeholder_end(datetime(2026, 1, 1, 0, 30, 0, tzinfo=UTC))
    assert not _is_placeholder_end(datetime(2026, 1, 15, 0, 0, 0, tzinfo=UTC))


def test_israel_pm_pair_confirms_with_real_prod_timestamps():
    """Israel-PM pair + REAL VERIFY112 locks -> confidence >= 0.50 confirmed."""
    match = match_venue_markets(
        A1_PM,
        A1_KS,
        pm_slug="pm-will-itamar-ben-gvir-be-the-next-prime-minister-of-israel",
        ks_slug="ks-kxnextisraelpm-45jan01-iben",
        pm_close_time=PROD_PM_LOCK,
        ks_close_time=PROD_KS_LOCK,
        pm_event_id="0x95f2c1a4-condition-id",
        ks_event_id="KXNISRAELPM-26",
        min_confidence=PERSIST_FLOOR,
    )
    assert "resolution_date_reject" not in match.reasons
    assert any(r.startswith("resolution_date_soft_pass") for r in match.reasons)
    assert match.confidence >= PERSIST_FLOOR
    assert match.status == "confirmed"
