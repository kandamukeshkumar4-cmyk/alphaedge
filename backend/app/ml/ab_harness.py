"""Resolved-count watcher + LightGBM vs XGBoost walk-forward A/B harness (G06).

Owner-action #4: the LightGBM comparison only becomes meaningful once enough
REAL resolved outcomes exist. This module provides:

* :func:`count_resolved_outcomes` — the resolved-count watcher, using the same
  real-resolution sources as ``GET /api/v1/track-record`` (scored LIVE
  forecasts on resolved external markets, falling back to resolved
  paper-order markets). One source of truth, no fabricated counts.
* :func:`resolved_count_readout` — admin/script readout of the count and
  whether the A/B gate (``>= MIN_RESOLVED_FOR_AB``) is met.
* :func:`run_walk_forward_ab` — when (and only when) the gate is met, runs the
  EXISTING walk-forward trainer twice (once per model type) and records BOTH
  out-of-sample Briers. Below the gate it reports the count and exits cleanly
  without touching the trainer.

HARD GUARDRAIL: this harness NEVER flips the default model. The deployed
model stays whatever ``ML_MODEL_TYPE`` says (default ``xgboost``); the readout
merely reports both Briers so a human can decide later. When lightgbm is not
installed, ``build_classifier`` falls back to XGBoost — the readout records
that honestly (``used_fallback_xgboost``) instead of pretending a LightGBM
result exists.

Run as a script: ``python -m app.ml.ab_harness`` (prints the count readout).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import get_settings
from app.ml.model_registry import LIGHTGBM_AVAILABLE
from app.ml.trainer import train_walk_forward_xgboost_from_feature_matrix

# Gate: the A/B runs only at or above this many real resolved outcomes.
MIN_RESOLVED_FOR_AB = 100

AB_MODEL_TYPES = ("xgboost", "lightgbm")


async def count_resolved_outcomes(session) -> int:
    """Count real resolved outcomes — same definition as track-record's ``n``."""
    return int((await resolved_outcomes_breakdown(session))["count"])


async def resolved_outcomes_breakdown(session) -> dict[str, Any]:
    """Which population ``count_resolved_outcomes`` actually counted (V33 B2'c).

    Pure disclosure, no new semantics: the preference order and the resulting
    ``count`` are exactly what ``count_resolved_outcomes`` has always returned,
    so the A/B gate is unaffected. It just stops being silent about the source.

    ``source`` is ``"forecast_scores"`` when the count comes from scored
    pre-close forecasts (the population the forecast loops accrue), or
    ``"paper_orders_fallback"`` when it falls back to resolved paper orders —
    a *different* population, which the readout previously reported as if it
    were the same number.
    """
    from app.api.v1.calibration import _from_paper_orders
    from app.api.v1.track_record import _resolved_forecast_rows

    rows = await _resolved_forecast_rows(session)
    forecast_scored_count = len(rows)
    if rows:
        return {
            "count": forecast_scored_count,
            "source": "forecast_scores",
            "forecast_scored_count": forecast_scored_count,
        }
    predictions, _, _ = await _from_paper_orders(session)
    return {
        "count": len(predictions),
        "source": "paper_orders_fallback",
        "forecast_scored_count": 0,
    }


async def resolved_count_readout(session) -> dict[str, Any]:
    """Admin/script readout: resolved count + A/B gate status."""
    settings = get_settings()
    resolved_count = await count_resolved_outcomes(session)
    return {
        "paper_trading_only": True,
        "resolved_count": resolved_count,
        "min_resolved_for_ab": MIN_RESOLVED_FOR_AB,
        "ab_eligible": resolved_count >= MIN_RESOLVED_FOR_AB,
        "default_model": settings.ml_model_type,
        "lightgbm_available": LIGHTGBM_AVAILABLE,
    }


def run_walk_forward_ab(
    df: pd.DataFrame | None,
    artifact_dir: Path,
    *,
    resolved_count: int,
    train_window_size: int,
    eval_window_size: int,
    min_resolved: int = MIN_RESOLVED_FOR_AB,
) -> dict[str, Any]:
    """LightGBM vs XGBoost walk-forward A/B over a feature matrix.

    Below ``min_resolved`` this reports the count and exits cleanly — the
    trainer is never invoked and ``df`` may be None. At or above the gate both
    model types are trained walk-forward on the SAME folds and both Briers are
    recorded. The default model is never changed here.
    """
    settings = get_settings()
    result: dict[str, Any] = {
        "paper_trading_only": True,
        "resolved_count": resolved_count,
        "min_resolved_for_ab": min_resolved,
        # The harness reports; it never flips the deployed default.
        "default_model": settings.ml_model_type,
        "default_model_changed": False,
        "lightgbm_available": LIGHTGBM_AVAILABLE,
        "ran": False,
    }
    if resolved_count < min_resolved:
        result["reason"] = "insufficient_resolved_outcomes"
        return result
    if df is None:
        raise ValueError("a feature matrix is required once the A/B gate is met")

    arms: dict[str, dict[str, Any]] = {}
    for model_type in AB_MODEL_TYPES:
        run = train_walk_forward_xgboost_from_feature_matrix(
            df,
            artifact_dir / model_type,
            train_window_size,
            eval_window_size,
            model_type=model_type,
        )
        arms[model_type] = {
            "model_type_requested": model_type,
            "used_fallback_xgboost": (
                model_type == "lightgbm" and not LIGHTGBM_AVAILABLE
            ),
            "model_brier": run["walk_forward"]["model_brier"],
            "closing_brier": run["walk_forward"]["closing_brier"],
            "count": run["walk_forward"]["count"],
        }

    result["ran"] = True
    result["arms"] = arms
    result["brier_delta_lightgbm_minus_xgboost"] = round(
        arms["lightgbm"]["model_brier"] - arms["xgboost"]["model_brier"], 6
    )
    return result


async def _main() -> None:  # pragma: no cover - manual admin script
    import json

    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        readout = await resolved_count_readout(session)
    print(json.dumps(readout, indent=2))


if __name__ == "__main__":  # pragma: no cover - manual admin script
    import asyncio

    asyncio.run(_main())
