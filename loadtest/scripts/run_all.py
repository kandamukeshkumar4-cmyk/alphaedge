#!/usr/bin/env python3
"""One-command Loop V20 runner: L1 smoke → L2 read-path → L3 trade+429.

Always local-only. Does not touch backend/frontend source.

Usage (repo root):
  py -3.13 loadtest/scripts/run_all.py
  py -3.13 loadtest/scripts/run_all.py --skip-onset
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(__file__).resolve().parent


def _run(label: str, argv: list[str]) -> int:
    print(f"\n======== {label} ========\n", flush=True)
    proc = subprocess.run([sys.executable, *argv], cwd=str(REPO_ROOT), check=False)
    print(f"\n======== {label} exit={proc.returncode} ========\n", flush=True)
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Loop V20 full baseline runner")
    parser.add_argument("--skip-onset", action="store_true")
    parser.add_argument("--port", type=int, default=18020)
    args = parser.parse_args(argv)

    steps = [
        (
            "L1 smoke",
            [
                str(SCRIPTS / "run_smoke.py"),
                "--port",
                str(args.port),
                "--users",
                "20",
                "--run-time",
                "60s",
            ],
        ),
        (
            "L2 read-path",
            [
                str(SCRIPTS / "run_read_path.py"),
                "--port",
                str(args.port),
                "--users",
                "15",
                "--run-time",
                "120s",
            ],
        ),
        (
            "L3 trade-path",
            [
                str(SCRIPTS / "run_trade_path.py"),
                "--port",
                str(args.port),
                "--users",
                "5",
                "--run-time",
                "90s",
            ]
            + (["--skip-onset"] if args.skip_onset else []),
        ),
    ]

    for label, cmd in steps:
        code = _run(label, cmd)
        if code != 0:
            print(f"[run_all] STOPPED at {label} with code {code}", flush=True)
            return code

    print(
        "[run_all] L1–L3 complete. See loadtest/results/ and "
        "loadtest/results/PERF-BASELINE.md for the frozen report.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
