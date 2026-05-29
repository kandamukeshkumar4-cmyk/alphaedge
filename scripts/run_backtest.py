#!/usr/bin/env python3
"""Run backtest against fixtures and print proof metrics."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import PAPER_TRADING_DISCLAIMER
from app.backtesting.replay import run_backtest

FIXTURES = ROOT / "fixtures"


def main() -> None:
    print(PAPER_TRADING_DISCLAIMER)
    print()
    result = run_backtest(FIXTURES, ROOT / "backend" / "ml_artifacts")
    print(json.dumps(result, indent=2))
    print()
    print(
        f"Backtested {result['market_count']} historical NBA markets\n"
        f"Brier Score: {result['brier_score']:.4f} · "
        f"Max Drawdown: {result['max_drawdown']:.2%} · "
        f"ROI: {result['roi']:.2%} · "
        f"Calibration Error: {result['calibration_error']:.4f}"
    )


if __name__ == "__main__":
    main()
