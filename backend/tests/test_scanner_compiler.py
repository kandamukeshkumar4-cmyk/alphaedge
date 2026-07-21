"""C2 — deterministic NL → scanner spec compiler."""
from app.services.scanner_compiler_service import compile_scanner_spec

# Spec-doc style example (whale + trend + news + schedule + universe + top-N).
SPEC_DOC_EXAMPLE = (
    "Scan NBA sports markets every 30 minutes for whale flow and 7 day price "
    "trend with news sentiment, volume above 10000, top 10"
)


def test_compile_spec_doc_example_sentence():
    spec = compile_scanner_spec(SPEC_DOC_EXAMPLE)
    types = [s["type"] for s in spec["steps"]]
    assert types == [
        "WHALE_FLOW",
        "PRICE_TREND",
        "NEWS_SENTIMENT",
        "DIRECTION_ALIGNMENT",
    ]
    trend = next(s for s in spec["steps"] if s["type"] == "PRICE_TREND")
    assert trend["window_days"] == 7
    assert spec["schedule"]["interval_minutes"] == 30
    assert spec["limit"] == 10
    assert "nba" in spec["universe"]["categories"]
    assert "sports" in spec["universe"]["categories"]
    assert spec["universe"]["minimum_volume"] == 10000
    assert spec["delivery"]["in_app"] is True
    assert "timezone" in spec["schedule"]


def test_compile_model_edge_daily_top_n():
    spec = compile_scanner_spec(
        "Watch crypto election markets daily for model edge, min volume 5000, top 5"
    )
    types = [s["type"] for s in spec["steps"]]
    assert "MODEL_EDGE" in types
    # Single signal step → no DIRECTION_ALIGNMENT
    assert "DIRECTION_ALIGNMENT" not in types
    assert spec["schedule"]["interval_minutes"] == 1440
    assert spec["limit"] == 5
    assert spec["universe"]["minimum_volume"] == 5000
    assert "crypto" in spec["universe"]["categories"]
    assert "election" in spec["universe"]["categories"]


def test_compile_unknown_text_still_valid_with_notes():
    spec = compile_scanner_spec("xyzzy plugh frobozz")
    assert isinstance(spec["steps"], list)
    assert spec["schedule"]["interval_minutes"] == 60
    assert spec["limit"] == 20
    assert spec["universe"]["categories"] == []
    assert spec["universe"]["minimum_volume"] == 0
    assert "delivery" in spec
    assert "notes" in spec
    assert "xyzzy" in spec["notes"]
    assert "plugh" in spec["notes"]
    assert "frobozz" in spec["notes"]
