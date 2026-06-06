#!/usr/bin/env python3
"""Run backtest against fixtures and print proof metrics."""

import json
import os
import shutil
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
UV_REEXEC_ENV = "ALPHAEDGE_BACKTEST_UV_REEXEC"


def _ensure_backend_environment() -> None:
    try:
        import joblib  # noqa: F401
    except ModuleNotFoundError as error:
        if error.name != "joblib":
            raise
        if os.environ.get(UV_REEXEC_ENV) == "1":
            raise SystemExit(
                "Backend dependency joblib is unavailable after uv re-exec."
            ) from error
        uv = shutil.which("uv")
        if uv is None:
            raise SystemExit(
                "Backend dependencies are unavailable. Run with "
                "`uv run --project backend python scripts/run_backtest.py`."
            ) from error
        env = os.environ.copy()
        env[UV_REEXEC_ENV] = "1"
        command = [
            uv,
            "run",
            "--project",
            str(BACKEND),
            "python",
            str(Path(__file__).resolve()),
            *sys.argv[1:],
        ]
        raise SystemExit(subprocess.call(command, cwd=ROOT, env=env)) from error


_ensure_backend_environment()
sys.path.insert(0, str(ROOT / "backend"))

from app import PAPER_TRADING_DISCLAIMER
from app.backtesting.replay import run_backtest

FIXTURES = ROOT / "fixtures"


def _parse_args(argv: list[str] | None = None):
    parser = ArgumentParser(description="Run AlphaEdge fixture backtest proof metrics.")
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=FIXTURES,
        help="Directory containing odds, games, and final-score fixture CSVs.",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=ROOT / "backend" / "ml_artifacts",
        help="Directory for persisted model and calibrator artifacts.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Optional path to write the full machine-readable backtest result JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    print(PAPER_TRADING_DISCLAIMER)
    print()
    result = run_backtest(args.fixtures, args.artifact_dir)
    rendered = json.dumps(result, indent=2)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    print()
    print(
        f"Backtested {result['market_count']} historical NBA markets\n"
        f"Brier Score: {result['brier_score']:.4f} · "
        f"Max Drawdown: {result['max_drawdown']:.2%} · "
        f"ROI: {result['roi']:.2%} · "
        f"Calibration Error: {result['calibration_error']:.4f}"
    )
    phase3 = result["phase3_forecast_gate"]
    walk_forward = phase3["walk_forward"]
    print(
        "Phase 3 forecast gate: "
        f"{phase3['gate']} · "
        f"CLV {walk_forward['mean_clv']:.4f} · "
        f"Brier {walk_forward['model_brier']:.4f} vs "
        f"closing {walk_forward['closing_brier']:.4f}"
    )
    if phase3["gate"] != "met":
        print(f"Phase 3 blockers: {', '.join(phase3['blocked_reasons'])}")
        print(f"Phase 3 sample shortfall: {phase3['sample_shortfall']}")


if __name__ == "__main__":
    main()
