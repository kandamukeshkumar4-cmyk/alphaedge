"""H1/H2/H3 — scanner self-heal classifier, repairs, and API visibility."""
from __future__ import annotations

import pytest

from app.services.scanner_heal_service import (
    EmptyResponseError,
    classify_step_error,
    coerce_numeric_strings,
)


@pytest.mark.parametrize(
    "exc,expected",
    [
        (ValueError("could not convert string to float: 'x'"), "type_mismatch"),
        (TypeError("int() argument must be a string, not 'list'"), "type_mismatch"),
        (KeyError("pressure"), "missing_field"),
        (AttributeError("'NoneType' object has no attribute 'yes_price'"), "missing_field"),
        (EmptyResponseError([]), "empty_response"),
        (ValueError("empty list"), "empty_response"),
        (RuntimeError("HTTP 429 rate limit exceeded"), "rate_limited"),
        (RuntimeError("provider rate exceeded"), "rate_limited"),
        (LookupError("404 market slug nba-2025-01-15-lal-bos not found"), "invalid_market"),
        (RuntimeError("market locked: lock_at in the past"), "expired_market"),
        (TimeoutError("upstream timeout after 30s"), "provider_transient"),
        (RuntimeError("HTTP 503 temporarily unavailable"), "provider_transient"),
        (RuntimeError("something completely unexpected"), "unknown"),
    ],
)
def test_classify_step_error_eight_classes(exc, expected):
    assert classify_step_error(exc, context={"node": 0}) == expected


def test_classify_covers_all_eight_distinct_classes():
    samples = {
        "type_mismatch": ValueError("invalid literal for int() with base 10"),
        "missing_field": KeyError("reads"),
        "empty_response": EmptyResponseError("[]"),
        "rate_limited": Exception("429 Too Many Requests"),
        "invalid_market": Exception("slug=nba-bad-slug not found"),
        "expired_market": Exception("market closed in the past"),
        "provider_transient": Exception("502 Bad Gateway"),
        "unknown": Exception("no idea"),
    }
    got = {classify_step_error(e) for e in samples.values()}
    assert got == set(samples.keys())


def test_coerce_numeric_strings_guarded():
    assert coerce_numeric_strings({"window_days": "7", "name": "x"}) == {
        "window_days": 7.0,
        "name": "x",
    }
    assert coerce_numeric_strings(["1.5", "nope"]) == [1.5, "nope"]
