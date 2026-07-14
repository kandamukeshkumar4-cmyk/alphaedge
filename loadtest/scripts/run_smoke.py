#!/usr/bin/env python3
"""L1: boot local stack (if needed) + 20 VU / 60s locust smoke.

Writes:
  loadtest/results/smoke-<stamp>.csv  (locust stats)
  loadtest/results/smoke-<stamp>.md   (summary)
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOADTEST = REPO_ROOT / "loadtest"
RESULTS = LOADTEST / "results"
SCRIPTS = LOADTEST / "scripts"
SCENARIOS = LOADTEST / "scenarios"

# Ensure scenarios package is importable for locust.
sys.path.insert(0, str(LOADTEST))

from scripts.boot_local_stack import LocalStack, DEFAULT_PORT  # noqa: E402
from scenarios.common import assert_local_host  # noqa: E402


def _log(msg: str) -> None:
    print(f"[run_smoke] {msg}", flush=True)


def ensure_locust() -> str:
    """Return a command prefix that can run locust from loadtest deps."""
    uv = shutil.which("uv")
    if not uv:
        # Fallback: system locust
        locust = shutil.which("locust")
        if locust:
            return locust
        raise RuntimeError("uv not found and locust not on PATH")
    # Install/sync loadtest deps into an ephemeral uv env for this project.
    sync = subprocess.run(
        ["uv", "sync"],
        cwd=str(LOADTEST),
        check=False,
        capture_output=True,
        text=True,
    )
    if sync.returncode != 0:
        _log(sync.stdout)
        _log(sync.stderr)
        # pyproject package=false may skip; try bare pip install via uv
        install = subprocess.run(
            ["uv", "pip", "install", "--python", sys.executable, "locust", "httpx"],
            cwd=str(LOADTEST),
            check=False,
            capture_output=True,
            text=True,
        )
        if install.returncode != 0:
            # Last resort: uv run --with
            return "uv-run-with"
    return "uv"


def run_locust(
    *,
    host: str,
    users: int,
    spawn_rate: int,
    run_time: str,
    csv_prefix: Path,
    locustfile: Path,
    html_report: Path | None = None,
) -> int:
    assert_local_host(host)
    RESULTS.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LOADTEST_HOST"] = host
    env["PYTHONPATH"] = str(LOADTEST) + os.pathsep + env.get("PYTHONPATH", "")

    base_cmd: list[str]
    uv = shutil.which("uv")
    if uv:
        # --with pulls locust without polluting backend pyproject
        base_cmd = [
            uv,
            "run",
            "--with",
            "locust",
            "--with",
            "httpx",
            "locust",
        ]
    else:
        base_cmd = ["locust"]

    cmd = base_cmd + [
        "-f",
        str(locustfile),
        "--host",
        host,
        "--users",
        str(users),
        "--spawn-rate",
        str(spawn_rate),
        "--run-time",
        run_time,
        "--headless",
        "--only-summary",
        "--csv",
        str(csv_prefix),
    ]
    if html_report is not None:
        cmd += ["--html", str(html_report)]

    _log(" ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(LOADTEST), env=env, check=False)
    return proc.returncode


def summarize_csv(csv_stats: Path, out_md: Path, meta: dict) -> dict:
    """Parse locust *_stats.csv into a short markdown summary."""
    rows: list[dict] = []
    if csv_stats.exists():
        with csv_stats.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

    def fnum(row: dict, *keys: str) -> float | None:
        for k in keys:
            if k in row and row[k] not in (None, ""):
                try:
                    return float(row[k])
                except ValueError:
                    continue
        return None

    lines = [
        "# L1 Smoke Results",
        "",
        f"- **stamp**: {meta.get('stamp')}",
        f"- **host**: `{meta.get('host')}` (local only)",
        f"- **users**: {meta.get('users')}",
        f"- **run_time**: {meta.get('run_time')}",
        f"- **spawn_rate**: {meta.get('spawn_rate')}",
        "",
        "| Name | #reqs | fails | p50 ms | p95 ms | p99 ms | avg ms |",
        "|------|------:|------:|-------:|-------:|-------:|-------:|",
    ]
    summary: dict = {"endpoints": []}
    for row in rows:
        name = row.get("Name") or row.get("name") or ""
        if name in ("", "Aggregated"):
            # still record Aggregated at end
            pass
        n = fnum(row, "Request Count", "# requests")
        fails = fnum(row, "Failure Count", "# failures")
        # Locust CSV columns vary by version
        p50 = fnum(row, "50%", "Median Response Time")
        p95 = fnum(row, "95%")
        p99 = fnum(row, "99%")
        avg = fnum(row, "Average Response Time")
        lines.append(
            f"| {name} | {int(n or 0)} | {int(fails or 0)} | "
            f"{p50 if p50 is not None else '—'} | "
            f"{p95 if p95 is not None else '—'} | "
            f"{p99 if p99 is not None else '—'} | "
            f"{avg if avg is not None else '—'} |"
        )
        summary["endpoints"].append(
            {
                "name": name,
                "requests": n,
                "failures": fails,
                "p50_ms": p50,
                "p95_ms": p95,
                "p99_ms": p99,
                "avg_ms": avg,
            }
        )

    lines.append("")
    lines.append(f"Raw CSV: `{csv_stats.relative_to(REPO_ROOT).as_posix()}`")
    lines.append("")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="L1 smoke load test")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--spawn-rate", type=int, default=10)
    parser.add_argument("--run-time", default="60s")
    parser.add_argument(
        "--external-host",
        default="",
        help="Use already-running local host (must be 127.0.0.1). Skips boot.",
    )
    args = parser.parse_args(argv)

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    RESULTS.mkdir(parents=True, exist_ok=True)
    csv_prefix = RESULTS / f"smoke-{stamp}"
    out_md = RESULTS / f"smoke-{stamp}.md"
    locustfile = SCENARIOS / "smoke.py"

    stack_cm = None
    host: str
    if args.external_host:
        host = assert_local_host(args.external_host)
        _log(f"using external local host {host}")
    else:
        stack_cm = LocalStack(port=args.port)
        stack_cm.__enter__()
        host = stack_cm.base_url

    try:
        # Brief settle
        time.sleep(0.5)
        code = run_locust(
            host=host,
            users=args.users,
            spawn_rate=args.spawn_rate,
            run_time=args.run_time,
            csv_prefix=csv_prefix,
            locustfile=locustfile,
        )
        stats_csv = Path(str(csv_prefix) + "_stats.csv")
        summarize_csv(
            stats_csv,
            out_md,
            {
                "stamp": stamp,
                "host": host,
                "users": args.users,
                "run_time": args.run_time,
                "spawn_rate": args.spawn_rate,
            },
        )
        _log(f"summary → {out_md}")
        if code != 0:
            _log(f"locust exit code {code}")
        # Soft-fail only if zero requests; otherwise surface summary even on failures.
        if stats_csv.exists():
            return 0 if code == 0 else code
        return code or 1
    finally:
        if stack_cm is not None:
            stack_cm.__exit__(None, None, None)


if __name__ == "__main__":
    raise SystemExit(main())
