"""Regenerate tests/fixtures/openapi_snapshot.json after an INTENTIONAL API change.

Usage (from backend/):  uv run python scripts/regen_openapi_snapshot.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.test_openapi_snapshot import SNAPSHOT_PATH, _current_surface  # noqa: E402

if __name__ == "__main__":
    surface = _current_surface()
    SNAPSHOT_PATH.write_text(
        json.dumps(surface, indent=1, sort_keys=True), encoding="utf-8"
    )
    print(f"wrote {SNAPSHOT_PATH} ({len(surface)} paths)")
