#!/usr/bin/env python3
"""L2: read-path baseline — markets/detail/candles/signals/leaderboard/portfolio/feed.

Writes loadtest/results/baseline-<date>.md + CSV stats.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOADTEST = REPO_ROOT / "loadtest"
RESULTS = LOADTEST / "results"
SCENARIOS = LOADTEST / "scenarios"

sys.path.insert(0, str(LOADTEST))

from scripts.boot_local_stack import DEFAULT_PORT, LocalStack  # noqa: E402
from scripts.locust_util import markdown_table, parse_stats_csv, run_locust  # noqa: E402
from scenarios.common import assert_local_host  # noqa: E402


def _log(msg: str) -> None:
    print(f"[run_read_path] {msg}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="L2 read-path baseline")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--users", type=int, default=15)
    parser.add_argument("--spawn-rate", type=int, default=5)
    parser.add_argument("--run-time", default="120s")
    parser.add_argument("--external-host", default="")
    args = parser.parse_args(argv)

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    date_slug = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    RESULTS.mkdir(parents=True, exist_ok=True)
    csv_prefix = RESULTS / f"readpath-{stamp}"
    out_md = RESULTS / f"baseline-{date_slug}.md"
    # Also keep stamp-specific copy for history.
    out_md_stamp = RESULTS / f"baseline-{stamp}.md"
    locustfile = SCENARIOS / "read_path.py"

    stack_cm = None
    if args.external_host:
        host = assert_local_host(args.external_host)
    else:
        stack_cm = LocalStack(port=args.port)
        stack_cm.__enter__()
        host = stack_cm.base_url

    try:
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
        rows = parse_stats_csv(stats_csv)
        body = "\n".join(
            [
                f"# L2 Read-path baseline — {date_slug}",
                "",
                f"- **stamp**: {stamp}",
                f"- **host**: `{host}` (local only)",
                f"- **users**: {args.users}",
                f"- **run_time**: {args.run_time}",
                f"- **spawn_rate**: {args.spawn_rate}",
                f"- **locust_exit**: {code}",
                f"- **raw CSV**: `{stats_csv.relative_to(REPO_ROOT).as_posix()}`",
                "",
                "## Latency & errors",
                "",
                markdown_table(rows),
                "",
                "## Notes",
                "",
                "- 404 on empty slices (signals/feed/candles) counted as success for baseline.",
                "- Global RATE_LIMIT 600/min/IP may produce 429s if pacing is aggressive.",
                "- Portfolio endpoints require per-VU signup (setup row excluded from product table when named).",
                "",
            ]
        )
        out_md.write_text(body, encoding="utf-8")
        out_md_stamp.write_text(body, encoding="utf-8")
        _log(f"baseline → {out_md}")
        return 0 if code == 0 else code
    finally:
        if stack_cm is not None:
            stack_cm.__exit__(None, None, None)


if __name__ == "__main__":
    raise SystemExit(main())
