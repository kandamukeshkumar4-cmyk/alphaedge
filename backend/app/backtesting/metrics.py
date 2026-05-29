from __future__ import annotations

import numpy as np


def brier_score(predictions: list[float], outcomes: list[int]) -> float:
    if not predictions:
        return 0.0
    return float(np.mean([(p - o) ** 2 for p, o in zip(predictions, outcomes)]))


def roi(pnls: list[float], initial_bankroll: float = 10000.0) -> float:
    if initial_bankroll <= 0:
        return 0.0
    return float(sum(pnls) / initial_bankroll)


def max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for v in equity_curve:
        peak = max(peak, v)
        dd = (peak - v) / peak if peak else 0
        max_dd = max(max_dd, dd)
    return float(max_dd)


def calibration_error(predictions: list[float], outcomes: list[int], bins: int = 10) -> float:
    if not predictions:
        return 0.0
    bucket_preds: dict[int, list[tuple[float, int]]] = {i: [] for i in range(bins)}
    for p, o in zip(predictions, outcomes):
        idx = min(int(p * bins), bins - 1)
        bucket_preds[idx].append((p, o))
    errors = []
    for items in bucket_preds.values():
        if not items:
            continue
        mean_p = np.mean([x[0] for x in items])
        mean_o = np.mean([x[1] for x in items])
        errors.append(abs(mean_p - mean_o))
    return float(np.mean(errors)) if errors else 0.0
