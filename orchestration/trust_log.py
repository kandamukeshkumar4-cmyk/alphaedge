"""Trust ledger: autonomy per skill, granted and revoked by measured pass rate.

    py -3.13 orchestration/trust_log.py log <skill> <pass|fail>
    py -3.13 orchestration/trust_log.py tier <skill>
    py -3.13 orchestration/trust_log.py report

Tiers: auto  = >=20 runs and >=95% pass  -> may run unattended
       queue = >=10 runs and >=90% pass  -> verified drafts wait for a human
       watch = everything else           -> draft-only, human reviews all
Demotion is automatic; it prints ALERT to stderr so schedulers surface it.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

LEDGER = Path(__file__).resolve().parent / "trust.tsv"


def entries() -> list[tuple[str, str, str]]:
    if not LEDGER.exists():
        return []
    rows = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            rows.append((parts[0], parts[1], parts[2]))
    return rows


def stats(skill: str) -> tuple[int, float]:
    runs = [r for r in entries() if r[1] == skill]
    if not runs:
        return 0, 0.0
    passes = sum(1 for r in runs if r[2] == "pass")
    return len(runs), passes / len(runs)


def tier(skill: str) -> str:
    n, rate = stats(skill)
    if n >= 20 and rate >= 0.95:
        return "auto"
    if n >= 10 and rate >= 0.90:
        return "queue"
    return "watch"


def main() -> int:
    argv = sys.argv[1:]
    if argv[:1] == ["log"] and len(argv) == 3 and argv[2] in ("pass", "fail"):
        before = tier(argv[1])
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now(UTC).isoformat()}\t{argv[1]}\t{argv[2]}\n")
        after = tier(argv[1])
        print(f"{argv[1]}: logged {argv[2]} -> tier {after}")
        order = ["watch", "queue", "auto"]
        if order.index(after) < order.index(before):
            print(f"ALERT: {argv[1]} demoted {before} -> {after}", file=sys.stderr)
        return 0
    if argv[:1] == ["tier"] and len(argv) == 2:
        print(tier(argv[1]))
        return 0
    if argv == ["report"]:
        skills = sorted({r[1] for r in entries()})
        for s in skills:
            n, rate = stats(s)
            print(f"{s}\truns={n}\tpass={rate:.0%}\ttier={tier(s)}")
        if not skills:
            print("(ledger empty)")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
