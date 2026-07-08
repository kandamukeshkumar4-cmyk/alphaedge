"""Deterministic completion gate. No model can overrule this script.

Usage:
    py -3.13 orchestration/gate.py                 # backend + frontend gates
    py -3.13 orchestration/gate.py --backend-only
    py -3.13 orchestration/gate.py --frontend-only
    py -3.13 orchestration/gate.py --prod          # also verify production

Exit 0 = the work may be called done. Anything else = it may not.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CHECKS_BACKEND = [
    ("backend pytest", ["py", "-3.13", "-m", "pytest", "-x", "-q"], ROOT / "backend"),
    ("backend ruff", ["py", "-3.13", "-m", "ruff", "check", "app", "tests"], ROOT / "backend"),
]
CHECKS_FRONTEND = [
    ("frontend typecheck", ["npx.cmd", "tsc", "--noEmit"], ROOT / "frontend"),
    ("frontend test", ["npm.cmd", "run", "test", "--", "--run"], ROOT / "frontend"),
    ("frontend build", ["npm.cmd", "run", "build"], ROOT / "frontend"),
]
CHECKS_PROD = [
    ("prod verifier", ["py", "-3.13", str(ROOT / "scripts" / "verify_prod.py")], ROOT),
]


def run(name: str, cmd: list[str], cwd: Path) -> bool:
    print(f"\n=== GATE: {name} ===", flush=True)
    try:
        proc = subprocess.run(cmd, cwd=cwd, timeout=1800)
    except FileNotFoundError as exc:
        print(f"FAIL {name}: command not found ({exc})")
        return False
    except subprocess.TimeoutExpired:
        print(f"FAIL {name}: timed out")
        return False
    ok = proc.returncode == 0
    print(f"{'PASS' if ok else 'FAIL'} {name} (exit {proc.returncode})")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend-only", action="store_true")
    ap.add_argument("--frontend-only", action="store_true")
    ap.add_argument("--prod", action="store_true")
    args = ap.parse_args()

    checks = []
    if not args.frontend_only:
        checks += CHECKS_BACKEND
    if not args.backend_only:
        checks += CHECKS_FRONTEND
    if args.prod:
        checks += CHECKS_PROD

    failures = [name for name, cmd, cwd in checks if not run(name, cmd, cwd)]
    print("\n=== GATE VERDICT ===")
    if failures:
        print("FAIL:", ", ".join(failures))
        return 1
    print("PASS: all checks green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
