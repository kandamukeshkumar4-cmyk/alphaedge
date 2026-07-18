"""ai-hedge-fund v2 alpha blend (app/forecasting/alpha).

Covers the v2-adapted contracts: abstention excluded from numerator AND
denominator, conviction<->probability mapping, spec loading that fails loud
on typos, and the predictor integration (blend only ever replaces the
artifact producer path).
"""

import joblib
import pytest

from app.forecasting.alpha import (
    ALPHA_MODEL_REGISTRY,
    AlphaSignal,
    BlendSpec,
    blend_market_probability,
    blend_signals,
    default_blend_spec,
    load_blend_spec,
)
from app.forecasting.alpha.models import ArtifactModel, MarketImpliedModel
from app.forecasting.predictor import (
    PRODUCER_ALPHA_BLEND,
    PRODUCER_ARTIFACT,
    predict_market,
)


class FeatureEchoModel:
    def predict_proba(self, rows):
        yes = float(rows[0][0]) + float(rows[0][1])
        return [[1.0 - yes, yes]]


class OffsetCalibrator:
    def predict(self, probabilities):
        return [float(probabilities[0]) + 0.05]


# ---------------------------------------------------------------------------
# Signal / conviction mapping
# ---------------------------------------------------------------------------

def test_signal_probability_conviction_roundtrip():
    signal = AlphaSignal.from_probability("artifact", 0.75)
    assert signal.value == pytest.approx(0.5)
    assert signal.probability == pytest.approx(0.75)
    assert signal.abstained is False


def test_abstained_signal_is_not_a_tossup_vote():
    abstain = AlphaSignal.abstain("artifact", "no artifact")
    vote = AlphaSignal.from_probability("market_implied", 0.8)
    result = blend_signals([abstain, vote], {"artifact": 0.4, "market_implied": 0.6})
    # The abstainer is out of numerator AND denominator: pure market view.
    assert result.probability == pytest.approx(0.8)
    assert result.abstained == ["artifact"]
    assert result.weights == {"market_implied": pytest.approx(1.0)}


def test_all_abstaining_returns_none():
    signals = [AlphaSignal.abstain("artifact", "x"), AlphaSignal.abstain("market_implied", "y")]
    assert blend_signals(signals, {"artifact": 1.0, "market_implied": 1.0}) is None


def test_blend_is_weighted_mean_in_probability_space():
    signals = [
        AlphaSignal.from_probability("artifact", 0.70),
        AlphaSignal.from_probability("market_implied", 0.50),
    ]
    result = blend_signals(signals, {"artifact": 0.4, "market_implied": 0.6})
    assert result.probability == pytest.approx(0.4 * 0.70 + 0.6 * 0.50)
    assert result.disagreement > 0
    assert result.contributions == {
        "artifact": pytest.approx(0.70),
        "market_implied": pytest.approx(0.50),
    }


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

def test_market_implied_model_reads_implied_and_abstains_without_it():
    model = MarketImpliedModel()
    assert model.predict({"implied_yes": 0.62}).probability == pytest.approx(0.62)
    assert model.predict({}).abstained is True


def test_artifact_model_reads_injected_probability_and_abstains_without_it():
    model = ArtifactModel()
    assert model.predict({"artifact_probability": 0.7}).probability == pytest.approx(0.7)
    assert model.predict({}).abstained is True


def test_models_reject_out_of_range_probabilities():
    with pytest.raises(ValueError):
        MarketImpliedModel().predict({"implied_yes": 1.5})
    with pytest.raises(ValueError):
        ArtifactModel().predict({"artifact_probability": -0.1})


# ---------------------------------------------------------------------------
# Spec — mandates as data, typos fail loud
# ---------------------------------------------------------------------------

def test_spec_rejects_unknown_model_and_extra_keys(tmp_path):
    bad_model = tmp_path / "bad_model.yaml"
    bad_model.write_text("name: x\nmodels:\n  - name: nonexistent\n")
    with pytest.raises(ValueError, match="unknown alpha model"):
        load_blend_spec(bad_model)

    typo = tmp_path / "typo.yaml"
    typo.write_text("name: x\nmodles:\n  - name: artifact\n")
    with pytest.raises(ValueError):
        load_blend_spec(typo)


def test_spec_rejects_duplicate_models_and_nonpositive_weights():
    with pytest.raises(ValueError, match="duplicate"):
        BlendSpec(
            name="dup",
            models=[{"name": "artifact"}, {"name": "artifact"}],
        )
    with pytest.raises(ValueError):
        BlendSpec(name="w", models=[{"name": "artifact", "weight": 0}])


def test_default_spec_loads_shipped_yaml_and_registry_is_buildable():
    spec = default_blend_spec()
    assert set(spec.model_weights) == {"artifact", "market_implied"}
    built = spec.build_models()
    assert {model.name for model in built} == set(ALPHA_MODEL_REGISTRY) & set(
        spec.model_weights
    )


# ---------------------------------------------------------------------------
# blend_market_probability — the caller-facing seam
# ---------------------------------------------------------------------------

def test_blend_market_probability_blends_artifact_toward_market():
    result = blend_market_probability({"implied_yes": 0.50}, artifact_probability=0.70)
    assert 0.50 < result.probability < 0.70


def test_blend_market_probability_none_when_all_abstain():
    assert blend_market_probability({}) is None


# ---------------------------------------------------------------------------
# predict_market integration
# ---------------------------------------------------------------------------

def _artifact_features(tmp_path, **overrides):
    model_path = tmp_path / "model.joblib"
    calibrator_path = tmp_path / "calibrator.joblib"
    joblib.dump(FeatureEchoModel(), model_path)
    joblib.dump(OffsetCalibrator(), calibrator_path)
    features = {
        "implied_yes": 0.55,
        "elo_diff": 0.10,
        "model_artifact_path": str(model_path),
        "calibrator_path": str(calibrator_path),
        "feature_columns": ["implied_yes", "elo_diff"],
    }
    features.update(overrides)
    return features


def test_predict_market_blends_artifact_with_market_when_enabled(tmp_path):
    prediction = predict_market(_artifact_features(tmp_path, alpha_blend_enabled=True))
    spec = default_blend_spec()
    weights = spec.model_weights
    expected = weights["artifact"] * 0.70 + weights["market_implied"] * 0.55
    assert prediction.predicted_prob == pytest.approx(expected)
    assert prediction.producer == PRODUCER_ALPHA_BLEND


def test_predict_market_blend_off_serves_raw_artifact(tmp_path):
    prediction = predict_market(_artifact_features(tmp_path, alpha_blend_enabled=False))
    assert prediction.predicted_prob == pytest.approx(0.70)
    assert prediction.producer == PRODUCER_ARTIFACT


def test_predict_market_never_blends_supplied_or_passthrough_paths():
    supplied = predict_market(
        {"implied_yes": 0.55, "model_probability": 0.65, "alpha_blend_enabled": True}
    )
    assert supplied.predicted_prob == pytest.approx(0.65)
    passthrough = predict_market({"implied_yes": 0.55, "alpha_blend_enabled": True})
    assert passthrough.predicted_prob == pytest.approx(0.55)
