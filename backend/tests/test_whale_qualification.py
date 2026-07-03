"""T05 — whale qualification: each rule boundary + one-hit-wonder exclusion."""
from __future__ import annotations

from decimal import Decimal

from app.signals.smart_money import WalletStats, qualify_whale


def _stats(resolved=60, wins=42, gross_profit="1000", gross_loss="500", top_win="200"):
    return WalletStats(
        resolved_count=resolved,
        wins=wins,
        gross_profit=Decimal(gross_profit),
        gross_loss=Decimal(gross_loss),
        top_win=Decimal(top_win),
    )


def test_fully_qualified_wallet_passes():
    # 60 resolved, 70% acc, PF 2.0, top win 200/500 total = 0.40 share... exactly 0.40
    # -> use top_win 199 so share < 0.40
    s = _stats(top_win="199")
    result = qualify_whale(s)
    assert result.qualified is True
    assert result.reasons == ()


def test_resolved_count_boundary():
    assert qualify_whale(_stats(resolved=49, wins=40, top_win="199")).qualified is False
    assert qualify_whale(_stats(resolved=50, wins=40, top_win="199")).qualified is True


def test_accuracy_boundary():
    # 65% of 60 = 39 wins is the boundary
    assert qualify_whale(_stats(wins=38, top_win="199")).qualified is False  # 63.3%
    assert qualify_whale(_stats(wins=39, top_win="199")).qualified is True  # 65.0%


def test_profit_factor_boundary():
    # PF exactly 1.5 passes; below fails
    at = _stats(gross_profit="1500", gross_loss="1000", top_win="199")  # PF 1.5
    below = _stats(gross_profit="1499", gross_loss="1000", top_win="199")  # PF 1.499
    assert qualify_whale(at).qualified is True
    assert "profit_factor<1.5" in qualify_whale(below).reasons


def test_one_hit_wonder_excluded():
    # total_pnl = 1000-500 = 500; top_win 200 -> share 0.40 == max -> excluded
    result = qualify_whale(_stats(top_win="200"))
    assert result.qualified is False
    assert "one_hit_wonder" in result.reasons
    # just under 0.40 share qualifies
    assert qualify_whale(_stats(top_win="199")).qualified is True


def test_no_losses_infinite_profit_factor_still_checks_other_rules():
    s = WalletStats(
        resolved_count=60, wins=45,
        gross_profit=Decimal("1000"), gross_loss=Decimal("0"), top_win=Decimal("100"),
    )
    # PF infinite passes PF rule; top_win 100/1000 = 0.10 share ok; 45/60=75% ok
    assert qualify_whale(s).qualified is True


def test_negative_book_is_treated_as_concentrated():
    s = WalletStats(
        resolved_count=60, wins=40,
        gross_profit=Decimal("100"), gross_loss=Decimal("300"), top_win=Decimal("50"),
    )
    # total_pnl negative -> top_win_share = 1.0 -> one_hit_wonder guard fires
    assert "one_hit_wonder" in qualify_whale(s).reasons
