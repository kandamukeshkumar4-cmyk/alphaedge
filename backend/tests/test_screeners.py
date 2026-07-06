"""O03: deterministic expiry-fade + momentum screeners (pure rules)."""

from app.signals.screeners import screen_expiry_fade, screen_momentum


# ── momentum ────────────────────────────────────────────────────────────────


def test_momentum_flags_clean_upward_drift():
    hit = screen_momentum("mkt", [0.30, 0.34, 0.40, 0.46])
    assert hit is not None
    assert hit.kind == "momentum"
    assert hit.direction == "up"
    # net move 0.16 / scale 0.40 = 0.40
    assert hit.strength == 0.4
    assert hit.detail["net_move"] == 0.16


def test_momentum_flags_clean_downward_drift():
    hit = screen_momentum("mkt", [0.70, 0.62, 0.55, 0.50])
    assert hit is not None
    assert hit.direction == "down"


def test_momentum_rejects_reversal():
    # net move 0.08 meets the threshold, but the middle step reverses.
    assert screen_momentum("mkt", [0.30, 0.45, 0.38]) is None


def test_momentum_rejects_small_move():
    assert screen_momentum("mkt", [0.30, 0.32, 0.34]) is None  # net 0.04 < 0.08


def test_momentum_rejects_too_few_points():
    assert screen_momentum("mkt", [0.30, 0.50]) is None


def test_momentum_rejects_flat_series():
    assert screen_momentum("mkt", [0.40, 0.40, 0.40, 0.40]) is None


def test_momentum_caps_strength_at_one():
    hit = screen_momentum("mkt", [0.05, 0.30, 0.60, 0.95])
    assert hit is not None
    assert hit.strength == 1.0


# ── expiry fade ───────────────────────────────────────────────────────────────


def test_expiry_fade_flags_near_expiry_longshot():
    hit = screen_expiry_fade("mkt", implied_yes=0.08, hours_to_close=6.0)
    assert hit is not None
    assert hit.kind == "expiry_fade"
    assert hit.direction == "fade"
    assert 0.6 < hit.strength < 0.75
    assert hit.detail["hours_to_close"] == 6.0


def test_expiry_fade_ignores_non_longshot():
    assert screen_expiry_fade("mkt", implied_yes=0.55, hours_to_close=6.0) is None


def test_expiry_fade_ignores_far_expiry():
    assert screen_expiry_fade("mkt", implied_yes=0.08, hours_to_close=200.0) is None


def test_expiry_fade_ignores_missing_close():
    assert screen_expiry_fade("mkt", implied_yes=0.08, hours_to_close=None) is None


def test_expiry_fade_ignores_already_resolved_dust():
    # below min_prob — effectively resolved, nothing left to fade
    assert screen_expiry_fade("mkt", implied_yes=0.001, hours_to_close=6.0) is None


def test_expiry_fade_deeper_longshot_scores_higher():
    shallow = screen_expiry_fade("mkt", implied_yes=0.14, hours_to_close=6.0)
    deep = screen_expiry_fade("mkt", implied_yes=0.02, hours_to_close=6.0)
    assert shallow is not None and deep is not None
    assert deep.strength > shallow.strength
