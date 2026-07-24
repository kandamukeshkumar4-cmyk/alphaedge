from app.alpha.factors import FACTOR_FUNCTIONS


def test_every_factor_returns_a_normalized_score_with_provenance():
    features = {
        "model_probability": 0.70,
        "market_implied_probability": 0.50,
        "whale_flow": -0.40,
        "price_history": [0.40, 0.50, 0.60],
        "news_signal": 0.60,
        "sentiment_debate": 0.20,
        "hours_to_lock": 24,
        "edge": 0.80,
        "polymarket_probability": 0.45,
        "kalshi_probability": 0.55,
    }

    results = {name: function(features) for name, function in FACTOR_FUNCTIONS.items()}

    assert set(results) == {
        "model_edge",
        "whale_flow",
        "momentum",
        "mean_reversion",
        "news_sentiment",
        "time_decay",
        "cross_venue",
    }
    assert all(-1.0 <= result["score"] <= 1.0 for result in results.values())
    assert all(result["provenance"]["available"] for result in results.values())
    assert results["model_edge"]["score"] == 1.0
    assert results["whale_flow"]["score"] == -0.4
    assert results["momentum"]["score"] == 1.0
    assert results["mean_reversion"]["score"] == -1.0
    assert results["news_sentiment"]["score"] == 0.4
    assert results["time_decay"]["score"] == 0.4
    assert results["cross_venue"]["score"] == 1.0


def test_factor_missing_input_is_an_honest_zero_with_a_reason():
    result = FACTOR_FUNCTIONS["cross_venue"]({"polymarket_probability": 0.50})

    assert result == {
        "name": "cross_venue",
        "score": 0.0,
        "provenance": {
            "available": False,
            "reason": "missing_mirrored_venue_probability",
        },
    }
