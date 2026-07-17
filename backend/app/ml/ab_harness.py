"""Controlled V40 forecast-score XGBoost-vs-LightGBM A/B readout.

The public API is deliberately read-only: it reads a population summary and a
previously persisted ``JobRun`` result. Model fitting is only performed by the
explicit controlled refresh function below. The harness never changes the
deployed default model, creates orders, or reads the legacy snapshot matrix.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Iterable

import numpy as np
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import JobRun
from app.ml.forecast_ab_dataset import (
    DEFAULT_EMBARGO_RESOLVED_ROWS,
    DEFAULT_EVAL_WINDOW_SIZE,
    DEFAULT_TRAIN_WINDOW_SIZE,
    FORECAST_AB_FEATURE_COLUMNS,
    build_v40_folds,
    load_forecast_score_rows,
    population_summary,
)

# Binding V40 §B-6 / ORCHESTRATOR-AMENDMENT A1. This is correlation clusters,
# not a nominal row count and not a parameter to tune against observed results.
MIN_CORRELATION_CLUSTERS_FOR_AB = 100
DECISION_RELEVANT_DELTA = 0.01
MAX_SIGMA_D_FOR_POWER = 0.045
BOOTSTRAP_SAMPLES = 1_000
AB_READOUT_JOB_NAME = "forecast_model_ab_readout"
AB_MODEL_TYPES = ("xgboost", "lightgbm")


async def count_resolved_outcomes(session) -> int:
    """Legacy resolved-count disclosure; it is never the V51 A/B gate."""
    return int((await resolved_outcomes_breakdown(session))["count"])


async def resolved_outcomes_breakdown(session) -> dict[str, Any]:
    """Disclose the older count's source without allowing it into V51 training."""
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


async def forecast_score_population_readout(session) -> dict[str, Any]:
    """Cheap population preflight used by public read-only endpoints."""
    rows = await load_forecast_score_rows(session)
    summary = population_summary(rows)
    summary["ab_cluster_threshold"] = MIN_CORRELATION_CLUSTERS_FOR_AB
    summary["ab_ready"] = (
        summary["dataset_source"] == "forecast_scores"
        and summary["correlation_clusters"] >= MIN_CORRELATION_CLUSTERS_FOR_AB
    )
    return summary


async def resolved_count_readout(session) -> dict[str, Any]:
    """Compatibility readout with the V51 effective-n gate made explicit."""
    settings = get_settings()
    legacy = await resolved_outcomes_breakdown(session)
    population = await forecast_score_population_readout(session)
    return {
        "paper_trading_only": True,
        "resolved_count": legacy["count"],
        "source": legacy["source"],
        "forecast_scored_count": population["forecast_scored_count"],
        "correlation_clusters": population["correlation_clusters"],
        "ab_threshold": MIN_CORRELATION_CLUSTERS_FOR_AB,
        "ab_ready": population["ab_ready"],
        "default_model": settings.ml_model_type,
        "lightgbm_available": lightgbm_available(),
        "population": population,
    }


async def latest_controlled_ab_readout(session) -> dict[str, Any] | None:
    """Return the last controlled result, never calculate one during a GET."""
    row = await session.scalar(
        select(JobRun)
        .where(JobRun.job_name == AB_READOUT_JOB_NAME, JobRun.status == "success")
        .order_by(JobRun.finished_at.desc(), JobRun.id.desc())
        .limit(1)
    )
    if row is None or not isinstance(row.summary, dict):
        return None
    return dict(row.summary)


async def refresh_controlled_ab_readout(session) -> dict[str, Any]:
    """Run the bounded comparison under an explicit controlled invocation.

    This intentionally is not registered as a public endpoint. Callers own the
    transaction so a scheduler/ops runner can persist the result atomically.
    """
    settings = get_settings()
    rows = await load_forecast_score_rows(session)
    result = run_forecast_score_ab(
        rows,
        model_type_history_verified=settings.ab_model_type_history_verified,
        model_type_history_evidence=settings.ab_model_type_history_evidence,
    )
    now = datetime.now(UTC)
    session.add(
        JobRun(
            job_name=AB_READOUT_JOB_NAME,
            status="success",
            started_at=now,
            finished_at=now,
            summary=result,
        )
    )
    await session.flush()
    return result


def run_forecast_score_ab(
    rows: Iterable[dict[str, Any]],
    *,
    model_type_history_verified: bool = False,
    model_type_history_evidence: str = "",
    bootstrap_samples: int = BOOTSTRAP_SAMPLES,
    seed: int = 12_345,
) -> dict[str, Any]:
    """Evaluate both distinct model arms on V40-safe forecast-score folds."""
    materialized = list(rows)
    population = population_summary(materialized)
    settings = get_settings()
    result: dict[str, Any] = {
        "paper_trading_only": True,
        "dataset_source": "forecast_scores",
        "default_model": settings.ml_model_type,
        "default_model_changed": False,
        "applied": False,
        "population": population,
        "split_policy": {
            "eval_order": "locked_at_ascending",
            "train_predicate": "resolved_at < T_eval_min",
            "eval_predicate": "locked_at >= T_eval_min",
            "embargo_resolved_rows": DEFAULT_EMBARGO_RESOLVED_ROWS,
            "train_window_size": DEFAULT_TRAIN_WINDOW_SIZE,
            "eval_window_size": DEFAULT_EVAL_WINDOW_SIZE,
        },
        "model_type_history": {
            "verified": bool(model_type_history_verified and model_type_history_evidence),
            "evidence": model_type_history_evidence.strip() or None,
        },
        "lightgbm_available": lightgbm_available(),
        "ran": False,
        "verdict": "no_winner",
        "reasons": [],
    }
    if not population["valid_for_ab"]:
        result["reasons"].append("invalid_forecast_score_population")
    if population["correlation_clusters"] < MIN_CORRELATION_CLUSTERS_FOR_AB:
        result["reasons"].append("insufficient_correlation_clusters")
    if not result["lightgbm_available"]:
        # Do not compare XGBoost with the registry's fallback XGBoost arm.
        result["reasons"].append("lightgbm_unavailable")
    if not result["model_type_history"]["verified"]:
        result["reasons"].append("model_type_history_unverified")
    if result["reasons"]:
        return result

    folds = build_v40_folds(materialized)
    if not folds:
        result["reasons"].append("insufficient_safe_folds")
        return result

    arms = {model_type: _evaluate_arm(folds, model_type) for model_type in AB_MODEL_TYPES}
    xgb_rows = arms["xgboost"]["row_results"]
    lgbm_rows = arms["lightgbm"]["row_results"]
    paired = [
        {
            "cluster": left["correlation_cluster"],
            "delta": (right["prediction"] - right["outcome"]) ** 2
            - (left["prediction"] - left["outcome"]) ** 2,
        }
        for left, right in zip(xgb_rows, lgbm_rows)
    ]
    uncertainty = _cluster_bootstrap(paired, samples=bootstrap_samples, seed=seed)
    result.update(
        {
            "ran": True,
            "folds": [
                {
                    "eval_min_locked_at": fold.eval_min_locked_at.isoformat(),
                    "train_count": len(fold.train_rows),
                    "eval_count": len(fold.eval_rows),
                    "embargoed_forecast_ids": fold.embargoed_forecast_ids,
                }
                for fold in folds
            ],
            "arms": {
                name: {key: value for key, value in arm.items() if key != "row_results"}
                for name, arm in arms.items()
            },
            "brier_delta_lightgbm_minus_xgboost": uncertainty["mean_delta"],
            "uncertainty": uncertainty,
        }
    )
    composition_passes = all(population["checks"].values())
    winner: str | None = None
    if uncertainty["sigma_d"] > MAX_SIGMA_D_FOR_POWER:
        result["reasons"].append("underpowered_sigma_d")
    if uncertainty["achieved_mde"] > DECISION_RELEVANT_DELTA:
        result["reasons"].append("underpowered_achieved_mde")
    if uncertainty["ci_lower"] <= 0.0 <= uncertainty["ci_upper"]:
        result["reasons"].append("paired_brier_interval_crosses_zero")
    if not composition_passes:
        result["reasons"].append("composition_gate_failed")
    if not result["reasons"]:
        winner = "lightgbm" if uncertainty["mean_delta"] < 0 else "xgboost"
    result["winner"] = winner
    result["verdict"] = winner or "no_winner"
    return result


def _evaluate_arm(folds, model_type: str) -> dict[str, Any]:
    from app.ml.model_registry import build_classifier
    from app.ml.trainer import ConstantProbabilityModel

    rows: list[dict[str, Any]] = []
    for fold in folds:
        train_x = _feature_matrix(fold.train_rows)
        train_y = np.asarray([int(row["actual_outcome"]) for row in fold.train_rows])
        if len(set(int(value) for value in train_y)) < 2:
            model = ConstantProbabilityModel(float(np.mean(train_y)))
        else:
            model = build_classifier(model_type)
            model.fit(train_x, train_y)
        eval_x = _feature_matrix(fold.eval_rows)
        probabilities = model.predict_proba(eval_x)[:, 1]
        for row, probability in zip(fold.eval_rows, probabilities):
            rows.append(
                {
                    "forecast_id": row["forecast_id"],
                    "correlation_cluster": row["correlation_cluster"],
                    "prediction": float(probability),
                    "outcome": int(row["actual_outcome"]),
                    "market_implied_probability": float(row["market_implied_probability"]),
                }
            )
    predictions = [row["prediction"] for row in rows]
    outcomes = [row["outcome"] for row in rows]
    implied = [row["market_implied_probability"] for row in rows]
    return {
        "model_type_requested": model_type,
        "model_brier": _mean_brier(predictions, outcomes),
        "cluster_weighted_brier": _cluster_weighted_brier(rows, "prediction"),
        "market_brier": _mean_brier(implied, outcomes),
        "count": len(rows),
        "ece": _ece_bins(predictions, outcomes),
        "feature_columns": list(FORECAST_AB_FEATURE_COLUMNS),
        "calibration": "none; no eval-label calibration is fitted",
        "row_results": rows,
    }


def _feature_matrix(rows: Iterable[dict[str, Any]]) -> np.ndarray:
    return np.asarray(
        [[float(row[column]) for column in FORECAST_AB_FEATURE_COLUMNS] for row in rows],
        dtype=float,
    )


def _mean_brier(probabilities: Iterable[float], outcomes: Iterable[int]) -> float:
    values = [(float(probability) - int(outcome)) ** 2 for probability, outcome in zip(probabilities, outcomes)]
    return float(np.mean(values)) if values else 0.0


def _cluster_weighted_brier(rows: Iterable[dict[str, Any]], key: str) -> float:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row["correlation_cluster"])].append(
            (float(row[key]) - int(row["outcome"])) ** 2
        )
    return float(np.mean([np.mean(values) for values in grouped.values()])) if grouped else 0.0


def _ece_bins(probabilities: list[float], outcomes: list[int], bins: int = 10) -> dict[str, Any]:
    grouped: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for probability, outcome in zip(probabilities, outcomes):
        grouped[min(int(float(probability) * bins), bins - 1)].append((float(probability), int(outcome)))
    details = []
    weighted_error = 0.0
    total = len(probabilities)
    for index, values in enumerate(grouped):
        if not values:
            continue
        predicted = float(np.mean([item[0] for item in values]))
        observed = float(np.mean([item[1] for item in values]))
        weighted_error += len(values) / total * abs(predicted - observed)
        details.append(
            {
                "bin_index": index,
                "count": len(values),
                "mean_predicted": predicted,
                "observed_frequency": observed,
            }
        )
    return {"value": weighted_error, "bins": details}


def _cluster_bootstrap(
    paired_rows: Iterable[dict[str, Any]], *, samples: int, seed: int
) -> dict[str, float | int]:
    groups: dict[str, list[float]] = defaultdict(list)
    for row in paired_rows:
        groups[str(row["cluster"])].append(float(row["delta"]))
    cluster_means = np.asarray([np.mean(values) for values in groups.values()], dtype=float)
    if not len(cluster_means):
        raise ValueError("cluster bootstrap needs evaluation rows")
    rng = np.random.default_rng(seed)
    estimates = np.asarray(
        [np.mean(rng.choice(cluster_means, size=len(cluster_means), replace=True)) for _ in range(samples)]
    )
    sigma_d = float(np.std(cluster_means, ddof=1)) if len(cluster_means) > 1 else 0.0
    # 80%-power MDE for a two-sided alpha=.05 comparison, matching the V40 B-6
    # n≈97 derivation (z_.975 + z_.80) * sigma / sqrt(n).
    achieved_mde = float(2.80 * sigma_d / np.sqrt(len(cluster_means)))
    return {
        "method": "paired_cluster_bootstrap",
        "cluster_count": len(cluster_means),
        "bootstrap_samples": samples,
        "mean_delta": float(np.mean(cluster_means)),
        "ci_lower": float(np.quantile(estimates, 0.025)),
        "ci_upper": float(np.quantile(estimates, 0.975)),
        "sigma_d": sigma_d,
        "achieved_mde": achieved_mde,
        "decision_relevant_delta": DECISION_RELEVANT_DELTA,
    }


def lightgbm_available() -> bool:
    from app.ml.model_registry import LIGHTGBM_AVAILABLE

    return bool(LIGHTGBM_AVAILABLE)
