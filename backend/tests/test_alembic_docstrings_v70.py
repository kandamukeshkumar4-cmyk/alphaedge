"""Loop V70: alembic 052/053 docstring Revises lines match code."""

from pathlib import Path

ALEMBIC = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _docstring_and_revisions(name: str) -> tuple[str, str, str]:
    text = (ALEMBIC / name).read_text(encoding="utf-8")
    # First triple-quoted block
    start = text.index('"""') + 3
    end = text.index('"""', start)
    doc = text[start:end]
    rev = ""
    down = ""
    for line in text.splitlines():
        if line.startswith("revision:"):
            rev = line.split("=", 1)[1].strip().strip('"')
        if line.startswith("down_revision:"):
            down = line.split("=", 1)[1].strip().split(",")[0].strip().strip('"')
    return doc, rev, down


def test_052_heartbeat_docstring_revises_matches_code():
    doc, rev, down = _docstring_and_revisions("052_heartbeat.py")
    assert rev == "052_heartbeat"
    assert down == "051_venue_gaps"
    assert "Revises: 051_venue_gaps" in doc
    assert "Revision ID: 052_heartbeat" in doc
    assert "051_heartbeat" not in doc
    assert "047_social" not in doc


def test_053_pods_docstring_revises_matches_code():
    doc, rev, down = _docstring_and_revisions("053_pods.py")
    assert rev == "053_pods"
    assert down == "052_heartbeat"
    assert "Revises: 052_heartbeat" in doc
    assert "Revision ID: 053_pods" in doc
    assert "048_lock_provenance" not in doc
