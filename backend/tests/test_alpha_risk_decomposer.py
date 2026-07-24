from app.alpha.risk_decomposer import GENUINE_EDGE_T_STAT, decompose_oos_returns


def _factor_returns() -> dict[str, dict[str, float]]:
    return {"model_edge": {f"f-{index}": (index - 4) / 10 for index in range(10)}}


def test_decomposer_emits_no_signal_when_combined_return_is_explained_by_factor():
    factors = _factor_returns()
    result = decompose_oos_returns(dict(factors["model_edge"]), factors)

    assert result["status"] == "no_signal"
    assert result["reason"] == "residual_alpha_t_stat_below_threshold"
    assert result["residual_alpha_t_stat"] <= GENUINE_EDGE_T_STAT


def test_decomposer_only_emits_genuine_edge_from_checkable_residual_statistic():
    factors = _factor_returns()
    combined = {key: value + 0.1 for key, value in factors["model_edge"].items()}
    result = decompose_oos_returns(combined, factors)

    assert result["status"] == "genuine_edge"
    assert result["reason"] is None
    assert result["residual_alpha_t_stat"] > GENUINE_EDGE_T_STAT
    assert result["paper_trading_only"] is True


def test_decomposer_records_evidence_when_oos_sample_is_too_small():
    result = decompose_oos_returns({"a": 0.1}, {"model_edge": {"a": 0.1}})

    assert result["status"] == "no_signal"
    assert result["reason"] == "insufficient_oos_returns"
