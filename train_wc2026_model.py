#!/usr/bin/env python3
"""Train and persist the WC2026 XGBoost match forecaster (run once, not a test)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.ml.wc2026_model import DEFAULT_MODEL_PATH, train_and_save  # noqa: E402


def main() -> None:
    data_path = BACKEND / "app" / "data" / "fifa" / "intl_results.csv"
    train_and_save(str(data_path), str(DEFAULT_MODEL_PATH))
    print(f"Model saved to {DEFAULT_MODEL_PATH}")


if __name__ == "__main__":
    main()
