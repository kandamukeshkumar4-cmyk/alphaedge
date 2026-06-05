from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from sklearn.linear_model import LogisticRegression

from app.backtesting.metrics import brier_score, calibration_error


@dataclass(frozen=True)
class ReliabilityBin:
    bin_index: int
    lower: float
    upper: float
    count: int
    mean_predicted: float
    observed_rate: float
    absolute_error: float


@dataclass(frozen=True)
class CalibrationReport:
    raw_brier_score: float
    calibrated_brier_score: float
    raw_calibration_error: float
    calibrated_calibration_error: float
    improved: bool
    reliability_curve: list[ReliabilityBin]


@dataclass
class PlattCalibrator:
    model: LogisticRegression | None = None

    def predict(self, probabilities: Iterable[float]) -> list[float]:
        normalized = _probabilities(probabilities)
        if not normalized:
            return []
        if self.model is None:
            return normalized
        logits = np.array([_logit(probability) for probability in normalized]).reshape(-1, 1)
        return [float(probability) for probability in self.model.predict_proba(logits)[:, 1]]


def fit_platt_calibrator(probabilities: Iterable[float], outcomes: Iterable[int]) -> PlattCalibrator:
    normalized = _probabilities(probabilities)
    labels = _outcomes(outcomes)
    if len(normalized) != len(labels):
        raise ValueError("probabilities and outcomes must have the same length")
    if not normalized or len(set(labels)) < 2:
        return PlattCalibrator()

    model = LogisticRegression(random_state=0)
    logits = np.array([_logit(probability) for probability in normalized]).reshape(-1, 1)
    model.fit(logits, labels)
    return PlattCalibrator(model=model)


def calibration_report(
    raw_probabilities: Iterable[float],
    calibrated_probabilities: Iterable[float],
    outcomes: Iterable[int],
    bins: int = 10,
) -> CalibrationReport:
    raw = _probabilities(raw_probabilities)
    calibrated = _probabilities(calibrated_probabilities)
    labels = _outcomes(outcomes)
    if len(raw) != len(calibrated) or len(raw) != len(labels):
        raise ValueError("raw probabilities, calibrated probabilities, and outcomes must align")

    raw_brier = brier_score(raw, labels)
    calibrated_brier = brier_score(calibrated, labels)
    raw_error = calibration_error(raw, labels, bins=bins)
    calibrated_error = calibration_error(calibrated, labels, bins=bins)
    return CalibrationReport(
        raw_brier_score=raw_brier,
        calibrated_brier_score=calibrated_brier,
        raw_calibration_error=raw_error,
        calibrated_calibration_error=calibrated_error,
        improved=calibrated_error < raw_error and calibrated_brier <= raw_brier,
        reliability_curve=reliability_curve(calibrated, labels, bins=bins),
    )


def reliability_curve(
    probabilities: Iterable[float],
    outcomes: Iterable[int],
    bins: int = 10,
) -> list[ReliabilityBin]:
    if bins <= 0:
        raise ValueError("bins must be positive")
    normalized = _probabilities(probabilities)
    labels = _outcomes(outcomes)
    if len(normalized) != len(labels):
        raise ValueError("probabilities and outcomes must have the same length")
    if not normalized:
        return []

    buckets: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for probability, outcome in zip(normalized, labels):
        index = min(int(probability * bins), bins - 1)
        buckets[index].append((probability, outcome))

    curve: list[ReliabilityBin] = []
    for index, bucket in enumerate(buckets):
        if not bucket:
            continue
        mean_predicted = float(np.mean([item[0] for item in bucket]))
        observed_rate = float(np.mean([item[1] for item in bucket]))
        curve.append(
            ReliabilityBin(
                bin_index=index,
                lower=index / bins,
                upper=(index + 1) / bins,
                count=len(bucket),
                mean_predicted=mean_predicted,
                observed_rate=observed_rate,
                absolute_error=abs(mean_predicted - observed_rate),
            )
        )
    return curve


def _probabilities(values: Iterable[float]) -> list[float]:
    probabilities = [float(value) for value in values]
    for probability in probabilities:
        if probability < 0.0 or probability > 1.0:
            raise ValueError("probabilities must be between 0 and 1")
    return probabilities


def _outcomes(values: Iterable[int]) -> list[int]:
    outcomes = [int(value) for value in values]
    for outcome in outcomes:
        if outcome not in (0, 1):
            raise ValueError("outcomes must be 0 or 1")
    return outcomes


def _logit(probability: float) -> float:
    clipped = min(max(probability, 1e-6), 1.0 - 1e-6)
    return float(np.log(clipped / (1.0 - clipped)))
