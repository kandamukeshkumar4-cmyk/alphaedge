from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"
SCRIPT = ROOT / "scripts" / "run_backtest.py"


def test_run_backtest_cli_honors_repo_root_artifact_dir(tmp_path):
    artifact_dir = tmp_path / "phase3-artifacts"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "backend")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--fixtures",
            str(FIXTURES),
            "--artifact-dir",
            str(artifact_dir),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "Phase 3 forecast gate:" in result.stdout
    assert '"phase3_forecast_gate"' in result.stdout
    assert (artifact_dir / "xgboost_model.joblib").exists()
    assert (artifact_dir / "calibrator.joblib").exists()
    assert (artifact_dir / "phase3_walk_forward" / "xgboost_model.joblib").exists()


def test_run_backtest_cli_writes_json_report_and_summarizes_phase3_blockers(tmp_path):
    artifact_dir = tmp_path / "phase3-artifacts"
    report_path = tmp_path / "phase3-report.json"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "backend")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--fixtures",
            str(FIXTURES),
            "--artifact-dir",
            str(artifact_dir),
            "--json-output",
            str(report_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert report_path.exists()
    report = json.loads(report_path.read_text())
    phase3 = report["phase3_forecast_gate"]
    assert phase3["gate"] == "blocked"
    assert phase3["sample_shortfall"] == 99
    assert phase3["blocked_reasons"]
    assert "Phase 3 blockers: insufficient_resolved_sample" in result.stdout
    assert "Phase 3 sample shortfall: 99" in result.stdout


def test_run_backtest_cli_accepts_snapshot_feature_matrix(tmp_path):
    artifact_dir = tmp_path / "phase3-artifacts"
    matrix_path = tmp_path / "snapshot-matrix.json"
    report_path = tmp_path / "snapshot-report.json"
    matrix_path.write_text(json.dumps(_snapshot_feature_matrix_rows()), encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "backend")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--snapshot-matrix",
            str(matrix_path),
            "--artifact-dir",
            str(artifact_dir),
            "--json-output",
            str(report_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(report_path.read_text())
    phase3 = report["phase3_forecast_gate"]
    assert report["market_count"] == 10
    assert phase3["walk_forward"]["count"] == 6
    assert "Phase 3 forecast gate:" in result.stdout
    assert "snapshot matrix rows: 10" in result.stdout
    assert (artifact_dir / "phase3_snapshot_walk_forward" / "xgboost_model.joblib").exists()


def _snapshot_feature_matrix_rows() -> list[dict[str, object]]:
    rows = []
    for index in range(10):
        winner_yes = index % 2
        implied = 0.70 if winner_yes else 0.30
        opening = 0.40 if winner_yes else 0.60
        rows.append(
            {
                "market_slug": f"nba-2026-01-{index + 1:02d}-lal-bos",
                "captured_at": f"2026-01-{index + 1:02d}T17:00:00Z",
                "implied_yes": implied,
                "implied_no": 1.0 - implied,
                "opening_implied_yes": opening,
                "closing_implied": implied,
                "odds_movement": implied - opening,
                "line_move_velocity": (implied - opening) / 5,
                "snapshot_count": 2,
                "executable_yes_ask": implied + 0.02,
                "executable_no_ask": (1.0 - implied) + 0.02,
                "winner_yes": winner_yes,
                "label": winner_yes,
            }
        )
    return rows
