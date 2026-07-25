"""Loop110 — calibrated logistic baseline on lock-time forecast_scores features.

Trains on population A (LIVE resolved ForecastScore rows). Features are only
values knowable at lock time: market_implied_probability, time_to_resolution_hours,
and one-hot category from the lock-time AlphaFactorSnapshot (never a post-lock
taxonomy edit). Walk-forward uses build_v40_folds (embargo included).

Outputs match ``_artifact_probability``: joblib model (predict_proba), joblib
calibrator (predict), plus a feature_columns sidecar the legacy XGB trainer
omits. Never auto-activates a registry row.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence
from uuid import UUID

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtesting.metrics import brier_score
from app.db.models import AlphaClosingLine, AlphaFactorSnapshot
from app.forecasting.generic_artifact import (
    CALIBRATOR_FILENAME,
    CATEGORY_PREFIX,
    FEATURE_COLUMNS_FILENAME,
    MODEL_FILENAME,
    MODEL_NAME,
    category_column,
)
from app.ml.calibration import IdentityCalibrator, fit_best_calibrator
from app.ml.forecast_ab_dataset import (
    DEFAULT_EMBARGO_RESOLVED_ROWS,
    DEFAULT_EVAL_WINDOW_SIZE,
    DEFAULT_TRAIN_WINDOW_SIZE,
    FORECAST_AB_FEATURE_COLUMNS,
    build_v40_folds,
    load_forecast_score_rows,
)

logger = logging.getLogger(__name__)

DEFAULT_MIN_CATEGORY_COUNT = 5
BASE_FEATURE_COLUMNS = list(FORECAST_AB_FEATURE_COLUMNS)


@dataclass(frozen=True)
class ConstantProbabilityModel:
    """Fallback when a fold's train labels are a single class."""

    probability: float

    def predict_proba(self, rows: Sequence[Sequence[float]]) -> np.ndarray:
        p = float(self.probability)
        n = len(rows)
        return np.asarray([[1.0 - p, p] for _ in range(n)], dtype=float)


def locktime_feature_row(
    row: dict[str, Any],
    feature_columns: Sequence[str],
    *,
    categories: Sequence[str],
) -> list[float]:
    """Build one model row from lock-time fields only. Never invents values."""
    values: list[float] = []
    category = row.get("lock_category")
    if category is None:
        category = row.get("category")
    for column in feature_columns:
        if column in BASE_FEATURE_COLUMNS:
            value = row.get(column)
            if value is None:
                raise ValueError(f"missing lock-time feature: {column}")
            values.append(float(value))
            continue
        if column.startswith(CATEGORY_PREFIX):
            cat_name = column[len(CATEGORY_PREFIX) :]
            values.append(1.0 if category == cat_name else 0.0)
            continue
        raise ValueError(f"unknown feature column: {column}")
    # categories arg documents the vocabulary used to build columns; unused in
    # the numeric row itself beyond the one-hot match above.
    _ = categories
    return values


def select_categories(
    rows: Iterable[dict[str, Any]],
    *,
    min_count: int = DEFAULT_MIN_CATEGORY_COUNT,
) -> tuple[list[str], list[str]]:
    """Return (kept, dropped) category labels from lock-time category only."""
    counts: Counter[str] = Counter()
    for row in rows:
        category = row.get("lock_category")
        if category is None:
            category = row.get("category")
        if isinstance(category, str) and category.strip():
            counts[category.strip()] += 1
    kept = sorted(name for name, count in counts.items() if count >= min_count)
    dropped = sorted(name for name, count in counts.items() if count < min_count)
    return kept, dropped


def build_feature_columns(categories: Sequence[str]) -> list[str]:
    return list(BASE_FEATURE_COLUMNS) + [category_column(name) for name in categories]


async def enrich_locktime_fields(
    session: AsyncSession, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Overlay lock-time category + closing line; never re-reads live prices."""
    if not rows:
        return rows
    forecast_ids = [UUID(str(row["forecast_id"])) for row in rows]
    snapshots = (
        await session.execute(
            select(AlphaFactorSnapshot).where(
                AlphaFactorSnapshot.forecast_id.in_(forecast_ids)
            )
        )
    ).scalars().all()
    by_forecast = {str(snap.forecast_id): snap for snap in snapshots}
    closings = (
        await session.execute(
            select(AlphaClosingLine).where(
                AlphaClosingLine.forecast_id.in_(forecast_ids)
            )
        )
    ).scalars().all()
    closing_by_forecast = {
        str(line.forecast_id): float(line.closing_implied_probability)
        for line in closings
        if line.closing_implied_probability is not None
    }

    enriched: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        snap = by_forecast.get(str(row["forecast_id"]))
        lock_category = None
        if snap is not None:
            features = snap.features or {}
            raw = features.get("category")
            if isinstance(raw, str) and raw.strip():
                lock_category = raw.strip()
        # Prefer snapshot category (captured at lock). Fall back to the joined
        # ExternalMarket.category only when no snapshot exists — never invent.
        item["lock_category"] = lock_category if lock_category is not None else row.get("category")
        if str(row["forecast_id"]) in closing_by_forecast:
            item["closing_implied"] = closing_by_forecast[str(row["forecast_id"])]
        enriched.append(item)
    return enriched


async def load_generic_training_rows(session: AsyncSession) -> list[dict[str, Any]]:
    rows = await load_forecast_score_rows(session)
    return await enrich_locktime_fields(session, rows)


def _matrix(
    rows: Sequence[dict[str, Any]],
    feature_columns: Sequence[str],
    categories: Sequence[str],
) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(
        [locktime_feature_row(row, feature_columns, categories=categories) for row in rows],
        dtype=float,
    )
    y = np.asarray([int(row["actual_outcome"]) for row in rows], dtype=int)
    return x, y


def _fit_model(x: np.ndarray, y: np.ndarray):
    if len(set(int(v) for v in y)) < 2:
        return ConstantProbabilityModel(float(np.mean(y)))
    model = LogisticRegression(max_iter=1000, random_state=0)
    model.fit(x, y)
    return model


def _predict_proba(model, x: np.ndarray) -> list[float]:
    return [float(p) for p in model.predict_proba(x)[:, 1]]


def _fold_briers(
    *,
    model_probs: Sequence[float],
    implied: Sequence[float],
    closing: Sequence[float | None],
    outcomes: Sequence[int],
) -> dict[str, Any]:
    model_brier = brier_score(list(model_probs), list(outcomes))
    implied_brier = brier_score(list(implied), list(outcomes))
    closing_pairs = [
        (float(c), int(o))
        for c, o in zip(closing, outcomes)
        if c is not None
    ]
    if closing_pairs:
        closing_brier = brier_score(
            [p for p, _ in closing_pairs],
            [o for _, o in closing_pairs],
        )
    else:
        closing_brier = None
    return {
        "model_brier": model_brier,
        "implied_passthrough_brier": implied_brier,
        "closing_line_brier": closing_brier,
        "closing_line_n": len(closing_pairs),
        "n": len(outcomes),
    }


def train_generic_artifact(
    rows: Sequence[dict[str, Any]],
    artifact_dir: Path | str,
    *,
    min_category_count: int = DEFAULT_MIN_CATEGORY_COUNT,
    train_window_size: int = DEFAULT_TRAIN_WINDOW_SIZE,
    eval_window_size: int = DEFAULT_EVAL_WINDOW_SIZE,
    embargo_resolved_rows: int = DEFAULT_EMBARGO_RESOLVED_ROWS,
) -> dict[str, Any]:
    """Walk-forward train + persist model/calibrator/feature_columns sidecar."""
    materialized = [dict(row) for row in rows]
    # Drop rows missing base lock-time features — never fabricate.
    valid = [
        row
        for row in materialized
        if row.get("market_implied_probability") is not None
        and row.get("time_to_resolution_hours") is not None
        and row.get("actual_outcome") is not None
        and row.get("locked_at") is not None
        and row.get("resolved_at") is not None
        and row.get("close_at") is not None
    ]
    categories, dropped_categories = select_categories(
        valid, min_count=min_category_count
    )
    feature_columns = build_feature_columns(categories)

    folds = build_v40_folds(
        valid,
        train_window_size=train_window_size,
        eval_window_size=eval_window_size,
        embargo_resolved_rows=embargo_resolved_rows,
    )
    fold_metrics: list[dict[str, Any]] = []
    oos_model: list[float] = []
    oos_implied: list[float] = []
    oos_closing: list[float | None] = []
    oos_outcomes: list[int] = []

    for index, fold in enumerate(folds):
        x_train, y_train = _matrix(fold.train_rows, feature_columns, categories)
        x_eval, y_eval = _matrix(fold.eval_rows, feature_columns, categories)
        model = _fit_model(x_train, y_train)
        raw_train = _predict_proba(model, x_train)
        raw_eval = _predict_proba(model, x_eval)
        # Hold out the last train slice for calibrator validation when possible.
        if len(raw_train) >= 4 and len(set(int(v) for v in y_train)) >= 2:
            split = max(1, len(raw_train) // 5)
            calibrator = fit_best_calibrator(
                raw_train[:-split],
                list(y_train[:-split]),
                raw_train[-split:],
                list(y_train[-split:]),
            )
        else:
            calibrator = IdentityCalibrator()
        calibrated = calibrator.predict(raw_eval)
        implied = [float(row["market_implied_probability"]) for row in fold.eval_rows]
        closing = [
            float(row["closing_implied"]) if row.get("closing_implied") is not None else None
            for row in fold.eval_rows
        ]
        metrics = _fold_briers(
            model_probs=calibrated,
            implied=implied,
            closing=closing,
            outcomes=list(y_eval),
        )
        metrics["fold"] = index
        metrics["train_n"] = len(fold.train_rows)
        metrics["eval_n"] = len(fold.eval_rows)
        metrics["embargoed_forecast_ids"] = list(fold.embargoed_forecast_ids)
        fold_metrics.append(metrics)
        oos_model.extend(calibrated)
        oos_implied.extend(implied)
        oos_closing.extend(closing)
        oos_outcomes.extend(int(v) for v in y_eval)

    # Final fit on all valid rows (after walk-forward readout).
    x_all, y_all = _matrix(valid, feature_columns, categories)
    final_model = _fit_model(x_all, y_all)
    raw_all = _predict_proba(final_model, x_all)
    if len(raw_all) >= 4 and len(set(int(v) for v in y_all)) >= 2:
        split = max(1, len(raw_all) // 5)
        final_calibrator = fit_best_calibrator(
            raw_all[:-split],
            list(y_all[:-split]),
            raw_all[-split:],
            list(y_all[-split:]),
        )
    else:
        final_calibrator = IdentityCalibrator()

    overall = _fold_briers(
        model_probs=oos_model,
        implied=oos_implied,
        closing=oos_closing,
        outcomes=oos_outcomes,
    ) if oos_outcomes else {
        "model_brier": None,
        "implied_passthrough_brier": None,
        "closing_line_brier": None,
        "closing_line_n": 0,
        "n": 0,
    }

    out_dir = Path(artifact_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / MODEL_FILENAME
    calibrator_path = out_dir / CALIBRATOR_FILENAME
    sidecar_path = out_dir / FEATURE_COLUMNS_FILENAME
    joblib.dump(final_model, model_path)
    joblib.dump(final_calibrator, calibrator_path)
    sidecar = {
        "feature_columns": feature_columns,
        "categories": list(categories),
        "dropped_categories": list(dropped_categories),
        "min_category_count": min_category_count,
        "base_feature_columns": list(BASE_FEATURE_COLUMNS),
        "model_name": MODEL_NAME,
    }
    sidecar_path.write_text(json.dumps(sidecar, indent=2, sort_keys=True), encoding="utf-8")

    metrics = {
        "brier": overall.get("model_brier"),
        "brier_score": overall.get("model_brier"),
        "model_brier": overall.get("model_brier"),
        "implied_passthrough_brier": overall.get("implied_passthrough_brier"),
        "closing_line_brier": overall.get("closing_line_brier"),
        "brier_vs_closing_line": overall.get("closing_line_brier"),
        "closing_line_n": overall.get("closing_line_n"),
        "oos_n": overall.get("n"),
        "fold_metrics": fold_metrics,
        "train_rows": len(valid),
        "fold_count": len(folds),
        "categories": list(categories),
        "dropped_categories": list(dropped_categories),
        "feature_columns": feature_columns,
        "calibration_method": getattr(final_calibrator, "method", "unknown"),
    }
    return {
        "artifact_dir": str(out_dir),
        "artifact_path": str(model_path),
        "calibrator_path": str(calibrator_path),
        "feature_columns_path": str(sidecar_path),
        "feature_columns": feature_columns,
        "categories": list(categories),
        "dropped_categories": list(dropped_categories),
        "metrics": metrics,
        "model_name": MODEL_NAME,
        "activate": False,
    }


async def train_generic_artifact_from_session(
    session: AsyncSession,
    artifact_dir: Path | str,
    **kwargs: Any,
) -> dict[str, Any]:
    rows = await load_generic_training_rows(session)
    return train_generic_artifact(rows, artifact_dir, **kwargs)
