from decimal import Decimal

import joblib
import pytest

from app.agents.graph import run_agent_graph
from app.forecasting.predictor import predict_market


def _comparison(predicted: float, closing: float, outcome: int) -> dict:
    return {
        "predicted_prob": predicted,
        "closing_implied": closing,
        "outcome": outcome,
    }


def _trade(predicted: float, entry: float, closing: float) -> dict:
    return {
        "predicted_prob": predicted,
        "entry_implied": entry,
        "closing_implied": closing,
    }


def _executable_trade(
    predicted: float,
    yes_ask: float,
    no_ask: float,
    closing_yes: float,
) -> dict:
    return {
        "predicted_prob": predicted,
        "executable_yes_ask": yes_ask,
        "executable_no_ask": no_ask,
        "closing_yes": closing_yes,
    }


class FeatureEchoModel:
    def predict_proba(self, rows):
        yes = float(rows[0][0]) + float(rows[0][1])
        return [[1.0 - yes, yes]]


class OffsetCalibrator:
    def predict(self, probabilities):
        return [float(probabilities[0]) + 0.05]


def test_synthetic_non_edge_model_is_hidden():
    prediction = predict_market(
        {
            "implied_yes": 0.55,
            "model_probability": 0.55,
            "forecast_comparisons": [
                _comparison(predicted=0.50, closing=0.50, outcome=index % 2)
                for index in range(20)
            ],
            "edge_min_sample": 10,
            "edge_bootstrap_samples": 100,
        }
    )

    assert prediction.predicted_prob == pytest.approx(0.55)
    assert prediction.edge == pytest.approx(0.0)
    assert prediction.is_edge is False
    assert prediction.significance is not None
    assert prediction.significance.significant_beats_closing is False


def test_prediction_serves_calibrated_probability_from_persisted_model(tmp_path):
    model_path = tmp_path / "model.joblib"
    calibrator_path = tmp_path / "calibrator.joblib"
    joblib.dump(FeatureEchoModel(), model_path)
    joblib.dump(OffsetCalibrator(), calibrator_path)

    prediction = predict_market(
        {
            "implied_yes": 0.55,
            "elo_diff": 0.10,
            "model_artifact_path": str(model_path),
            "calibrator_path": str(calibrator_path),
            "feature_columns": ["implied_yes", "elo_diff"],
            # This test pins the raw artifact path; blend behavior is covered
            # in tests/test_alpha_blend.py.
            "alpha_blend_enabled": False,
        }
    )

    assert prediction.predicted_prob == pytest.approx(0.70)
    assert prediction.is_edge is False
    assert prediction.edge == pytest.approx(0.0)


def test_agent_prediction_requires_significant_closing_line_edge():
    state = run_agent_graph(
        "nba-2025-01-15-lal-bos",
        {
            "implied_yes": 0.55,
            "model_probability": 0.65,
            "forecast_comparisons": [
                _comparison(predicted=0.50, closing=0.50, outcome=index % 2)
                for index in range(20)
            ],
            "edge_min_sample": 10,
            "edge_bootstrap_samples": 100,
        },
    )

    assert state.predicted_prob == pytest.approx(0.65)
    assert state.features["forecast_is_edge"] is False
    assert state.order_intent is not None
    assert state.order_intent.edge == pytest.approx(0.0)
    assert state.approved is False
    assert "closing-line edge gate not met" in state.errors


def test_prediction_requires_positive_walk_forward_clv_before_crediting_edge():
    prediction = predict_market(
        {
            "implied_yes": 0.55,
            "model_probability": 0.70,
            "forecast_comparisons": [
                _comparison(
                    predicted=0.85 if index % 2 else 0.15,
                    closing=0.50,
                    outcome=index % 2,
                )
                for index in range(40)
            ],
            "edge_min_sample": 20,
            "edge_bootstrap_samples": 100,
        }
    )

    assert prediction.is_edge is False
    assert prediction.edge == pytest.approx(0.0)
    assert prediction.clv is None


def test_prediction_requires_positive_current_executable_edge_before_serving_edge():
    prediction = predict_market(
        {
            "implied_yes": 0.55,
            "executable_yes_ask": 0.75,
            "executable_no_ask": 0.40,
            "model_probability": 0.70,
            "forecast_comparisons": [
                _comparison(
                    predicted=0.85 if index % 2 else 0.15,
                    closing=0.50,
                    outcome=index % 2,
                )
                for index in range(40)
            ],
            "forecast_trades": [
                _trade(
                    predicted=0.85 if index % 2 else 0.15,
                    entry=0.50,
                    closing=0.65 if index % 2 else 0.35,
                )
                for index in range(40)
            ],
            "edge_min_sample": 20,
            "edge_bootstrap_samples": 100,
        }
    )

    assert prediction.is_edge is False
    assert prediction.edge == pytest.approx(0.0)
    assert prediction.reason == "executable price edge gate not met"


def test_agent_prediction_credits_significant_closing_line_edge_with_positive_clv():
    state = run_agent_graph(
        "nba-2025-01-15-lal-bos",
        {
            "implied_yes": 0.55,
            "model_probability": 0.70,
            "forecast_comparisons": [
                _comparison(
                    predicted=0.85 if index % 2 else 0.15,
                    closing=0.50,
                    outcome=index % 2,
                )
                for index in range(40)
            ],
            "forecast_trades": [
                _trade(
                    predicted=0.85 if index % 2 else 0.15,
                    entry=0.50,
                    closing=0.65 if index % 2 else 0.35,
                )
                for index in range(40)
            ],
            "edge_min_sample": 20,
            "edge_bootstrap_samples": 100,
        },
    )

    assert state.predicted_prob == pytest.approx(0.70)
    assert state.features["forecast_is_edge"] is True
    assert state.features["forecast_mean_clv"] == pytest.approx(0.15)
    assert state.order_intent is not None
    assert state.order_intent.edge == pytest.approx(0.15)
    assert state.approved is True


def test_agent_prediction_prices_edge_against_executable_ask_not_midpoint():
    state = run_agent_graph(
        "nba-2025-01-15-lal-bos",
        {
            "implied_yes": 0.55,
            "executable_yes_ask": 0.68,
            "executable_no_ask": 0.40,
            "model_probability": 0.70,
            "forecast_comparisons": [
                _comparison(
                    predicted=0.85 if index % 2 else 0.15,
                    closing=0.50,
                    outcome=index % 2,
                )
                for index in range(40)
            ],
            "forecast_trades": [
                _executable_trade(
                    predicted=0.85 if index % 2 else 0.15,
                    yes_ask=0.68,
                    no_ask=0.68,
                    closing_yes=0.75 if index % 2 else 0.25,
                )
                for index in range(40)
            ],
            "edge_min_sample": 20,
            "edge_bootstrap_samples": 100,
        },
    )

    assert state.predicted_prob == pytest.approx(0.70)
    assert state.features["forecast_is_edge"] is True
    assert state.features["forecast_edge"] == pytest.approx(0.02)
    assert state.order_intent is not None
    assert state.order_intent.price == Decimal("0.68")
    assert state.order_intent.edge == pytest.approx(0.02)
    assert state.approved is False
    assert any("edge 2.00% < 5%" in error for error in state.errors)
