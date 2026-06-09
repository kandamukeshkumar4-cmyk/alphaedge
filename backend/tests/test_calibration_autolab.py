"""Tests that verify the loop infrastructure STATE.md exists and is valid."""
from pathlib import Path


def test_state_md_exists():
    """STATE.md must exist at the repo root for the loop to resume correctly."""
    repo_root = Path(__file__).parent.parent.parent  # backend/../.. = repo root
    state_file = repo_root / "STATE.md"
    assert state_file.exists(), f"STATE.md not found at {state_file}"


def test_state_md_has_calibration_section():
    """STATE.md must contain the Calibration Metrics section for AutoLab tracking."""
    repo_root = Path(__file__).parent.parent.parent
    content = (repo_root / "STATE.md").read_text()
    assert "## Calibration Metrics" in content, \
        "STATE.md is missing '## Calibration Metrics' section"
