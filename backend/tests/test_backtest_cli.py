from __future__ import annotations

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
