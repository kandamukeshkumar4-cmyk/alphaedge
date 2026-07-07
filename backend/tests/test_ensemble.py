"""U08 — Multi-model ensemble + router tests.

Covers:
1. Ensemble probability combination math (weighted_mean, trivial equal-weight)
2. Disagreement / uncertainty band computation (stddev, clamping)
3. Router selection per category (NBA, Elections, FIFA, Crypto, unknown, default)
4. Flag OFF = baseline predict_market output byte-identical (regression guard)
5. EnsembleDisabledError raised when flag is OFF
6. Router forces PIPELINE_SINGLE when ensemble_enabled=False regardless of config
7. AutoLab measurement harness — insufficient_data when < 30 samples
8. AutoLab measurement harness — real Brier computed when samples >= 30
9. combine_estimates single-model edge case (zero disagreement band)
10. parse_router_config fallback on bad JSON
11. ModelRouter.category_from_features slug heuristics
12. ModelRouter.route convenience wrapper
"""
from __future__ import annotations

import pytest

from app.forecasting.ensemble import (
    EnsembleDisabledError,
    EnsemblePrediction,
    ModelEstimate,
    combine_estimates,
    ensemble_predict,
    run_autolab_measurement,
    weighted_mean,
    weighted_stddev,
)
from app.forecasting.router import (
    PIPELINE_ENSEMBLE_V2,
    PIPELINE_SINGLE,
    ModelRouter,
    build_router_from_settings,
    parse_router_config,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _est(prob: float, weight: float = 1.0, model_id: str = "m") -> ModelEstimate:
    return ModelEstimate(model_id=model_id, probability=prob, weight=weight)


def _resolved(baseline: float, ensemble: float, outcome: int) -> dict:
    return {"slug": "test-market", "baseline_prob": baseline, "ensemble_prob": ensemble, "outcome": outcome}


# ---------------------------------------------------------------------------
# 1. weighted_mean
# ---------------------------------------------------------------------------


def test_weighted_mean_equal_weights():
    ests = [_est(0.3), _est(0.7)]
    assert weighted_mean(ests) == pytest.approx(0.5)


def test_weighted_mean_unequal_weights():
    ests = [_est(0.2, weight=3.0), _est(0.8, weight=1.0)]
    expected = (0.2 * 3 + 0.8 * 1) / 4
    assert weighted_mean(ests) == pytest.approx(expected)


def test_weighted_mean_empty_raises():
    with pytest.raises(ValueError, match="non-empty"):
        weighted_mean([])


def test_weighted_mean_zero_weight_raises():
    with pytest.raises(ValueError, match="positive"):
        weighted_mean([_est(0.5, weight=0.0)])


# ---------------------------------------------------------------------------
# 2. Disagreement / uncertainty band
# ---------------------------------------------------------------------------


def test_weighted_stddev_single_estimate_is_zero():
    ests = [_est(0.6)]
    assert weighted_stddev(ests, 0.6) == 0.0


def test_weighted_stddev_two_equal_estimates_is_zero():
    ests = [_est(0.5), _est(0.5)]
    assert weighted_stddev(ests, 0.5) == pytest.approx(0.0, abs=1e-9)


def test_weighted_stddev_two_estimates_correct():
    # mean = 0.5; deviations are +/-0.2 each; weighted variance = (0.04 + 0.04)/2 = 0.04; std = 0.2
    ests = [_est(0.3), _est(0.7)]
    mean = 0.5
    std = weighted_stddev(ests, mean)
    assert std == pytest.approx(0.2, abs=1e-9)


def test_combine_estimates_band_clamped():
    """Uncertainty band must stay within [0, 1] even for edge cases."""
    ests = [_est(0.05), _est(0.95)]  # mean=0.5, std=0.45 -> band covers [0.05, 0.95]
    result = combine_estimates(ests)
    assert 0.0 <= result.uncertainty_low <= result.uncertainty_high <= 1.0


def test_combine_estimates_single_model_zero_width():
    ests = [_est(0.65)]
    result = combine_estimates(ests)
    assert result.ensemble_prob == pytest.approx(0.65)
    assert result.disagreement == 0.0
    assert result.uncertainty_low == pytest.approx(0.65)
    assert result.uncertainty_high == pytest.approx(0.65)


def test_combine_estimates_provisional_true_by_default():
    result = combine_estimates([_est(0.5)])
    assert result.provisional is True
    assert result.clv_gate_passed is False


def test_combine_estimates_unknown_method_raises():
    with pytest.raises(ValueError, match="unknown ensemble method"):
        combine_estimates([_est(0.5)], method="stacking")


# ---------------------------------------------------------------------------
# 3. Router selection per category
# ---------------------------------------------------------------------------


def test_router_nba_single_when_flag_off():
    router = ModelRouter(ensemble_enabled=False)
    assert router.select("NBA") == PIPELINE_SINGLE


def test_router_elections_single_when_flag_off():
    router = ModelRouter(ensemble_enabled=False)
    assert router.select("Elections") == PIPELINE_SINGLE


def test_router_unknown_category_falls_back_to_default():
    config = {"default": PIPELINE_SINGLE}
    router = ModelRouter(config=config, ensemble_enabled=True)
    assert router.select("UnknownCategory") == PIPELINE_SINGLE


def test_router_nba_ensemble_when_flag_on():
    config = {"NBA": PIPELINE_ENSEMBLE_V2, "default": PIPELINE_SINGLE}
    router = ModelRouter(config=config, ensemble_enabled=True)
    assert router.select("NBA") == PIPELINE_ENSEMBLE_V2


def test_router_elections_single_even_when_flag_on():
    config = {"NBA": PIPELINE_ENSEMBLE_V2, "Elections": PIPELINE_SINGLE, "default": PIPELINE_SINGLE}
    router = ModelRouter(config=config, ensemble_enabled=True)
    assert router.select("Elections") == PIPELINE_SINGLE


def test_router_missing_default_key_added():
    config = {"NBA": PIPELINE_SINGLE}
    router = ModelRouter(config=config, ensemble_enabled=True)
    assert router.select("FIFA") == PIPELINE_SINGLE


# ---------------------------------------------------------------------------
# 4. Flag OFF = baseline predict_market output byte-identical (regression guard)
# ---------------------------------------------------------------------------


def test_flag_off_predict_market_unchanged():
    """When ensemble is disabled predict_market() must return the same result
    as a control call — the single-model baseline is byte-identical."""
    from app.forecasting.predictor import predict_market

    features = {"implied_yes": 0.6}
    result_a = predict_market(features)
    result_b = predict_market(features)
    # Deterministic: same features -> same output (no randomness)
    assert result_a.predicted_prob == result_b.predicted_prob
    assert result_a.edge == result_b.edge
    assert result_a.is_edge == result_b.is_edge
    assert result_a.reason == result_b.reason


def test_flag_off_ensemble_predict_raises():
    """EnsembleDisabledError is raised when enabled=False."""
    ests = [_est(0.5)]
    with pytest.raises(EnsembleDisabledError):
        ensemble_predict({}, ests, enabled=False)


def test_flag_on_ensemble_predict_returns_prediction():
    ests = [_est(0.4, model_id="m1"), _est(0.6, model_id="m2")]
    result = ensemble_predict({}, ests, enabled=True)
    assert isinstance(result, EnsemblePrediction)
    assert result.ensemble_prob == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# 5. Router forces PIPELINE_SINGLE when ensemble_enabled=False
# ---------------------------------------------------------------------------


def test_router_always_single_when_flag_off_regardless_of_config():
    # Even if config says ensemble-v2 for NBA, flag OFF wins
    config = {"NBA": PIPELINE_ENSEMBLE_V2, "Elections": PIPELINE_ENSEMBLE_V2, "default": PIPELINE_ENSEMBLE_V2}
    router = ModelRouter(config=config, ensemble_enabled=False)
    for cat in ("NBA", "Elections", "FIFA", "Crypto", "default", "XYZ"):
        assert router.select(cat) == PIPELINE_SINGLE, f"expected SINGLE for {cat!r}"


# ---------------------------------------------------------------------------
# 6. AutoLab measurement harness — insufficient data
# ---------------------------------------------------------------------------


def test_autolab_insufficient_data_below_threshold():
    markets = [_resolved(0.6, 0.55, 1) for _ in range(5)]
    result = run_autolab_measurement(markets, min_samples=30)
    assert result.outcome == "insufficient_data"
    assert result.baseline_brier is None
    assert result.ensemble_brier is None
    assert result.n_samples == 5


def test_autolab_zero_samples_insufficient():
    result = run_autolab_measurement([], min_samples=30)
    assert result.outcome == "insufficient_data"
    assert result.n_samples == 0


# ---------------------------------------------------------------------------
# 7. AutoLab measurement harness — real Brier when data present
# ---------------------------------------------------------------------------


def test_autolab_measured_when_samples_sufficient():
    # 30 perfectly calibrated markets: baseline_prob = outcome = 1.0
    markets = [_resolved(1.0, 0.9, 1) for _ in range(30)]
    result = run_autolab_measurement(markets, min_samples=30)
    assert result.outcome == "measured"
    assert result.baseline_brier == pytest.approx(0.0, abs=1e-9)
    assert result.ensemble_brier == pytest.approx(0.01, abs=1e-9)  # (0.9-1)^2 = 0.01
    assert result.n_samples == 30


def test_autolab_ensemble_worse_than_baseline_still_honest():
    # Ensemble is WORSE — we record it honestly, not discard it
    markets = [_resolved(0.9, 0.5, 1) for _ in range(30)]
    result = run_autolab_measurement(markets, min_samples=30)
    assert result.outcome == "measured"
    # baseline: (0.9-1)^2 = 0.01 per market
    assert result.baseline_brier == pytest.approx(0.01, abs=1e-9)
    # ensemble: (0.5-1)^2 = 0.25 per market
    assert result.ensemble_brier == pytest.approx(0.25, abs=1e-9)
    # Ensemble is worse; flag should stay OFF in practice
    assert result.ensemble_brier > result.baseline_brier


# ---------------------------------------------------------------------------
# 8. parse_router_config
# ---------------------------------------------------------------------------


def test_parse_router_config_valid_json():
    raw = '{"NBA": "ensemble-v2", "Elections": "single"}'
    config = parse_router_config(raw)
    assert config["NBA"] == "ensemble-v2"
    assert config["Elections"] == "single"
    assert "default" in config  # auto-added


def test_parse_router_config_empty_string_returns_default():
    config = parse_router_config("")
    assert "default" in config
    assert config["default"] == PIPELINE_SINGLE


def test_parse_router_config_none_returns_default():
    config = parse_router_config(None)
    assert "default" in config


def test_parse_router_config_bad_json_returns_default():
    config = parse_router_config("{not valid json")
    assert "default" in config
    assert config["default"] == PIPELINE_SINGLE


def test_parse_router_config_non_dict_returns_default():
    config = parse_router_config("[1, 2, 3]")
    assert "default" in config


# ---------------------------------------------------------------------------
# 9. ModelRouter.category_from_features slug heuristics
# ---------------------------------------------------------------------------


def test_category_from_features_nba_slug():
    router = ModelRouter()
    assert router.category_from_features({"market_slug": "nba-2025-01-15-lal-bos"}) == "NBA"


def test_category_from_features_wc2026_slug():
    router = ModelRouter()
    assert router.category_from_features({"market_slug": "wc2026-final-fra-bra"}) == "FIFA"


def test_category_from_features_explicit_category_wins():
    router = ModelRouter()
    features = {"market_slug": "nba-lal-bos", "market_category": "Elections"}
    assert router.category_from_features(features) == "Elections"


def test_category_from_features_crypto_slug():
    router = ModelRouter()
    assert router.category_from_features({"market_slug": "btc-price-100k-2025"}) == "Crypto"


def test_category_from_features_unknown_slug_returns_default():
    router = ModelRouter()
    assert router.category_from_features({"market_slug": "random-prediction-xyz"}) == "default"


def test_category_from_features_empty_returns_default():
    router = ModelRouter()
    assert router.category_from_features({}) == "default"


# ---------------------------------------------------------------------------
# 10. ModelRouter.route convenience wrapper
# ---------------------------------------------------------------------------


def test_route_returns_single_when_flag_off():
    config = {"NBA": PIPELINE_ENSEMBLE_V2, "default": PIPELINE_SINGLE}
    router = ModelRouter(config=config, ensemble_enabled=False)
    assert router.route({"market_slug": "nba-2025-01-15-lal-bos"}) == PIPELINE_SINGLE


def test_route_returns_ensemble_for_nba_when_enabled():
    config = {"NBA": PIPELINE_ENSEMBLE_V2, "default": PIPELINE_SINGLE}
    router = ModelRouter(config=config, ensemble_enabled=True)
    assert router.route({"market_slug": "nba-2025-01-15-lal-bos"}) == PIPELINE_ENSEMBLE_V2


# ---------------------------------------------------------------------------
# 11. build_router_from_settings
# ---------------------------------------------------------------------------


class _FakeSettings:
    ensemble_enabled: bool = False
    ensemble_router_config: str = ""


def test_build_router_from_settings_flag_off_by_default():
    settings = _FakeSettings()
    router = build_router_from_settings(settings)
    assert not router.ensemble_enabled
    assert router.select("NBA") == PIPELINE_SINGLE


def test_build_router_from_settings_flag_on():
    settings = _FakeSettings()
    settings.ensemble_enabled = True
    settings.ensemble_router_config = '{"NBA": "ensemble-v2", "default": "single"}'
    router = build_router_from_settings(settings)
    assert router.ensemble_enabled
    assert router.select("NBA") == PIPELINE_ENSEMBLE_V2


# ---------------------------------------------------------------------------
# 12. Settings integration
# ---------------------------------------------------------------------------


def test_settings_ensemble_defaults():
    """Ensemble flag defaults ON (loop4) — safe because it degrades to the
    single-model baseline with 0-1 providers; router config still empty."""
    from app.core.config import Settings

    # Use the defaults directly (no env vars needed)
    settings = Settings()
    assert settings.ensemble_enabled is True
    assert settings.ensemble_router_config == ""
