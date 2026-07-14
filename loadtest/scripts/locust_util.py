"""Shared locust invoke + CSV summary helpers for Loop V20 runners."""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOADTEST = REPO_ROOT / "loadtest"
RESULTS = LOADTEST / "results"

sys.path.insert(0, str(LOADTEST))
from scenarios.common import assert_local_host  # noqa: E402


def run_locust(
    *,
    host: str,
    users: int,
    spawn_rate: int,
    run_time: str,
    csv_prefix: Path,
    locustfile: Path,
    extra_env: dict[str, str] | None = None,
    html_report: Path | None = None,
) -> int:
    assert_local_host(host)
    RESULTS.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LOADTEST_HOST"] = host
    env["PYTHONPATH"] = str(LOADTEST) + os.pathsep + env.get("PYTHONPATH", "")
    if extra_env:
        env.update(extra_env)

    uv = shutil.which("uv")
    if uv:
        base_cmd = [uv, "run", "--with", "locust", "--with", "httpx", "locust"]
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

    print(f"[locust_util] {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=str(LOADTEST), env=env, check=False).returncode


def fnum(row: dict, *keys: str) -> float | None:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            try:
                return float(row[k])
            except ValueError:
                continue
    return None


def parse_stats_csv(csv_stats: Path) -> list[dict]:
    rows: list[dict] = []
    if not csv_stats.exists():
        return rows
    with csv_stats.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row.get("Name") or row.get("name") or ""
            n = fnum(row, "Request Count", "# requests")
            fails = fnum(row, "Failure Count", "# failures")
            p50 = fnum(row, "50%", "Median Response Time")
            p95 = fnum(row, "95%")
            p99 = fnum(row, "99%")
            avg = fnum(row, "Average Response Time")
            rps = fnum(row, "Requests/s", "Requests/s")
            rows.append(
                {
                    "name": name,
                    "requests": int(n or 0),
                    "failures": int(fails or 0),
                    "p50_ms": p50,
                    "p95_ms": p95,
                    "p99_ms": p99,
                    "avg_ms": avg,
                    "rps": rps,
                    "error_rate": (fails / n) if n and n > 0 else 0.0,
                }
            )
    return rows


def markdown_table(rows: list[dict]) -> str:
    lines = [
        "| Name | #reqs | fails | err% | p50 ms | p95 ms | p99 ms | avg ms |",
        "|------|------:|------:|-----:|-------:|-------:|-------:|-------:|",
    ]
    for r in rows:
        err = f"{100.0 * r['error_rate']:.2f}" if r["requests"] else "—"
        def fmt(v):
            if v is None:
                return "—"
            if isinstance(v, float):
                return f"{v:.0f}" if v >= 10 else f"{v:.1f}"
            return str(v)

        lines.append(
            f"| {r['name']} | {r['requests']} | {r['failures']} | {err} | "
            f"{fmt(r['p50_ms'])} | {fmt(r['p95_ms'])} | {fmt(r['p99_ms'])} | {fmt(r['avg_ms'])} |"
        )
    return "\n".join(lines)
