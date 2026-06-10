from pathlib import Path

import pytest

from app.ml.wc2026_model import DEFAULT_MODEL_PATH, predict_match

DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data" / "fifa"


@pytest.mark.skipif(not DEFAULT_MODEL_PATH.exists(), reason="wc2026_model.pkl not trained")
def test_predict_match_probs_sum_to_one():
    p_home, p_draw, p_away = predict_match("ARG", "FRA", neutral=True)
    assert abs(p_home + p_draw + p_away - 1.0) < 1e-6
    assert all(p > 0 for p in (p_home, p_draw, p_away))


@pytest.mark.skipif(not DEFAULT_MODEL_PATH.exists(), reason="wc2026_model.pkl not trained")
def test_predict_match_strong_team_favored():
    p_home, _, _ = predict_match("BRA", "HAI", neutral=True)
    assert p_home > 0.45


@pytest.mark.skipif(not DEFAULT_MODEL_PATH.exists(), reason="wc2026_model.pkl not trained")
def test_predict_match_loads_from_serialized_pkl():
    p_home, p_draw, p_away = predict_match(
        "MEX",
        "RSA",
        neutral=True,
        model_path=str(DEFAULT_MODEL_PATH),
    )
    assert abs(p_home + p_draw + p_away - 1.0) < 1e-6
