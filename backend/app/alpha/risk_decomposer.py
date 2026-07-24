"""Out-of-sample residual-alpha test for a research weight vector."""

from __future__ import annotations

import math
from typing import Mapping


MIN_OOS_RETURNS = 8
GENUINE_EDGE_T_STAT = 2.5


def decompose_oos_returns(
    combined_returns: Mapping[str, float], factor_returns: Mapping[str, Mapping[str, float]]
) -> dict[str, object]:
    """Regress a combined research-return series on its component returns.

    The only positive conclusion is a numeric OOS residual-alpha t-stat above
    ``GENUINE_EDGE_T_STAT``.  All other outcomes are explicit evidence-backed
    no-signal results rather than a qualitative claim.
    """
    names = sorted(factor_returns)
    common_ids = sorted(set(combined_returns).intersection(*(set(factor_returns[name]) for name in names))) if names else []
    if len(common_ids) < max(MIN_OOS_RETURNS, len(names) + 2):
        return _no_signal("insufficient_oos_returns", len(common_ids))
    if not all(math.isfinite(float(combined_returns[item])) for item in common_ids):
        return _no_signal("non_finite_combined_return", len(common_ids))
    matrix = [[1.0, *[float(factor_returns[name][item]) for name in names]] for item in common_ids]
    target = [float(combined_returns[item]) for item in common_ids]
    coefficients, inverse = _least_squares(matrix, target)
    if coefficients is None or inverse is None:
        return _no_signal("collinear_factor_returns", len(common_ids))
    residuals = [
        observed - math.fsum(coefficient * feature for coefficient, feature in zip(coefficients, row))
        for observed, row in zip(target, matrix)
    ]
    degrees_of_freedom = len(target) - len(coefficients)
    if degrees_of_freedom <= 0:
        return _no_signal("insufficient_oos_returns", len(common_ids))
    residual_alpha = coefficients[0]
    residual_variance = math.fsum(value * value for value in residuals) / degrees_of_freedom
    alpha_standard_error = math.sqrt(max(0.0, residual_variance * inverse[0][0]))
    if alpha_standard_error <= 1e-12:
        t_stat = (
            999.0
            if residual_alpha > 1e-12
            else -999.0
            if residual_alpha < -1e-12
            else 0.0
        )
    else:
        t_stat = residual_alpha / alpha_standard_error
    genuine = t_stat > GENUINE_EDGE_T_STAT
    return {
        "status": "genuine_edge" if genuine else "no_signal",
        "reason": None if genuine else "residual_alpha_t_stat_below_threshold",
        "residual_alpha": round(residual_alpha, 8),
        "residual_alpha_t_stat": round(t_stat, 8),
        "threshold": GENUINE_EDGE_T_STAT,
        "oos_count": len(common_ids),
        "factor_betas": {name: round(coefficients[index + 1], 8) for index, name in enumerate(names)},
        "paper_trading_only": True,
    }


def _no_signal(reason: str, count: int) -> dict[str, object]:
    return {
        "status": "no_signal",
        "reason": reason,
        "residual_alpha": None,
        "residual_alpha_t_stat": None,
        "threshold": GENUINE_EDGE_T_STAT,
        "oos_count": count,
        "factor_betas": {},
        "paper_trading_only": True,
    }


def _least_squares(matrix: list[list[float]], target: list[float]):
    columns = len(matrix[0])
    normal = [
        [math.fsum(row[left] * row[right] for row in matrix) for right in range(columns)]
        for left in range(columns)
    ]
    rhs = [math.fsum(row[column] * value for row, value in zip(matrix, target)) for column in range(columns)]
    inverse = _invert(normal)
    if inverse is None:
        return None, None
    return [math.fsum(cell * value for cell, value in zip(row, rhs)) for row in inverse], inverse


def _invert(matrix: list[list[float]]) -> list[list[float]] | None:
    size = len(matrix)
    augmented = [row[:] + [1.0 if row_index == column else 0.0 for column in range(size)]
                 for row_index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) <= 1e-12:
            return None
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            scale = augmented[row][column]
            augmented[row] = [value - scale * pivot_value for value, pivot_value in zip(augmented[row], augmented[column])]
    return [row[size:] for row in augmented]
