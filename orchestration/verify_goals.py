"""Standing-goals sentinel: everything ever finished gets re-verified, forever.

Reads goals/standing/*.md, runs each `predicate:` line (a shell command;
exit 0 = the invariant still holds), and flips `status:` to VIOLATED on
failure. Detection only — fixes go through the normal work-order pipeline.

    py -3.13 orchestration/verify_goals.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOALS = ROOT / "goals" / "standing"


def main() -> int:
    if not GOALS.exists():
        print("no goals/standing directory; nothing to verify")
        return 0
    violated = []
    for path in sorted(GOALS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        pred = re.search(r"^predicate:\s*(.+)$", text, re.M)
        status = re.search(r"^status:\s*(\w+)", text, re.M)
        if not pred or (status and status.group(1) == "retired"):
            continue
        cmd = pred.group(1).strip()
        try:
            proc = subprocess.run(cmd, shell=True, cwd=ROOT, timeout=900,
                                  capture_output=True, text=True)
            ok = proc.returncode == 0
        except subprocess.TimeoutExpired:
            ok = False
        stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        new_status = "HOLDS" if ok else "VIOLATED"
        if status:
            text = re.sub(r"^status:.*$", f"status: {new_status} ({stamp})", text, count=1, flags=re.M)
        else:
            text = f"status: {new_status} ({stamp})\n" + text
        path.write_text(text, encoding="utf-8")
        print(f"{'PASS' if ok else 'FAIL'} {path.name}: {cmd}")
        if not ok:
            violated.append(path.name)
    if violated:
        print("\nVIOLATED:", ", ".join(violated))
        return 1
    print("\nall standing goals hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
