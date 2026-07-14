#!/usr/bin/env python3
"""L3: modest paper buy/close cycle + 429 onset probe.

1) Locust trade cycle (few VUs, paced) — expect zero 5xx.
2) Single-token hammer on POST /api/v1/orders until first 429 (or cap).

Writes loadtest/results/trade-<stamp>.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOADTEST = REPO_ROOT / "loadtest"
RESULTS = LOADTEST / "results"
SCENARIOS = LOADTEST / "scenarios"

sys.path.insert(0, str(LOADTEST))

from scripts.boot_local_stack import DEFAULT_PORT, LocalStack  # noqa: E402
from scripts.locust_util import markdown_table, parse_stats_csv, run_locust  # noqa: E402
from scenarios.common import (  # noqa: E402
    CANONICAL_SLUG,
    assert_local_host,
    unique_email,
)


def _log(msg: str) -> None:
    print(f"[run_trade_path] {msg}", flush=True)


def _http_json(
    method: str,
    url: str,
    *,
    body: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> tuple[int, dict | list | str | None, dict[str, str]]:
    data = None
    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            try:
                parsed: dict | list | str | None = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = raw
            return resp.status, parsed, {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed, {k.lower(): v for k, v in exc.headers.items()}


def probe_429_onset(host: str, *, max_attempts: int = 800) -> dict:
    """Hammer POST /api/v1/orders with one bearer token until 429 or cap.

    Mutating middleware default: RATE_LIMIT_MUTATING=600/minute per
    (token, method, path). Global slowapi also 600/minute per IP.
    """
    host = assert_local_host(host)
    email = unique_email("onset")
    status, tok_body, _ = _http_json(
        "POST",
        f"{host}/api/v1/auth/signup",
        body={"email": email, "password": "LoadTest20!"},
    )
    if status not in (200, 201) or not isinstance(tok_body, dict):
        return {
            "ok": False,
            "error": f"signup failed status={status} body={tok_body!r}",
        }
    token = tok_body.get("access_token")
    if not token:
        return {"ok": False, "error": "no access_token"}

    slug = CANONICAL_SLUG
    order_body = {
        "slug": slug,
        "side": "buy",
        "outcome": "yes",
        "shares": 1,
        "price": 0.5,
    }
    t0 = time.perf_counter()
    first_429_at: int | None = None
    first_429_elapsed_s: float | None = None
    first_429_retry_after: str | None = None
    status_counts: dict[str, int] = {}
    five_xx = 0
    success = 0

    for i in range(1, max_attempts + 1):
        headers = {
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": uuid.uuid4().hex[:32],
        }
        st, _body, resp_headers = _http_json(
            "POST",
            f"{host}/api/v1/orders",
            body=order_body,
            headers=headers,
            timeout=10.0,
        )
        key = str(st)
        status_counts[key] = status_counts.get(key, 0) + 1
        if st >= 500:
            five_xx += 1
        if st in (200, 201):
            success += 1
        if st == 429 and first_429_at is None:
            first_429_at = i
            first_429_elapsed_s = time.perf_counter() - t0
            first_429_retry_after = resp_headers.get("retry-after")
            # Continue a few more to confirm not fluke, then stop.
            # Actually stop soon after first 429 for clean onset number.
            break
        # Tiny yield so we don't freeze the interpreter; still aggressive.
        if i % 50 == 0:
            _log(f"429 probe progress attempts={i} statuses={status_counts}")

    elapsed = time.perf_counter() - t0
    return {
        "ok": True,
        "max_attempts": max_attempts,
        "attempts_until_stop": first_429_at or max_attempts,
        "first_429_at_attempt": first_429_at,
        "first_429_elapsed_s": first_429_elapsed_s,
        "first_429_retry_after": first_429_retry_after,
        "elapsed_s": elapsed,
        "success_2xx": success,
        "five_xx": five_xx,
        "status_counts": status_counts,
        "notes": (
            "Mutating limit default 600/minute per (token, POST, path); "
            "global RATE_LIMIT 600/minute per IP for all methods. "
            "Onset is first observed 429 under single-token hammer."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="L3 trade-path + 429 onset")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--users", type=int, default=5)
    parser.add_argument("--spawn-rate", type=int, default=2)
    parser.add_argument("--run-time", default="90s")
    parser.add_argument("--external-host", default="")
    parser.add_argument("--onset-max", type=int, default=800)
    parser.add_argument("--skip-onset", action="store_true")
    args = parser.parse_args(argv)

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    RESULTS.mkdir(parents=True, exist_ok=True)
    csv_prefix = RESULTS / f"trade-{stamp}"
    out_md = RESULTS / f"trade-{stamp}.md"
    locustfile = SCENARIOS / "trade_path.py"

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
        five_xx_rows = [r for r in rows if "5xx" in (r.get("name") or "").lower()]
        # Locust doesn't label 5xx in name; we track via failures. Parse failures CSV.
        failures_csv = Path(str(csv_prefix) + "_failures.csv")
        five_xx_count = 0
        if failures_csv.exists():
            text = failures_csv.read_text(encoding="utf-8", errors="replace")
            five_xx_count = text.count("5xx") + text.count("HTTPError('500") + text.count(
                "HTTPError('502"
            )

        onset: dict
        if args.skip_onset:
            onset = {"ok": True, "skipped": True}
        else:
            _log("starting 429 onset probe (single token hammer on POST /orders)")
            onset = probe_429_onset(host, max_attempts=args.onset_max)
            _log(f"429 onset result: {json.dumps(onset, default=str)[:500]}")

        lines = [
            f"# L3 Trade-path + 429 onset — {stamp}",
            "",
            f"- **host**: `{host}` (local only)",
            f"- **locust users**: {args.users}",
            f"- **run_time**: {args.run_time}",
            f"- **locust_exit**: {code}",
            f"- **raw CSV**: `{stats_csv.relative_to(REPO_ROOT).as_posix()}`",
            f"- **five_xx_in_failures_file**: {five_xx_count}",
            "",
            "## Trade cycle latency",
            "",
            markdown_table(rows),
            "",
            "## 429 onset probe",
            "",
            "```json",
            json.dumps(onset, indent=2, default=str),
            "```",
            "",
            "## Interpretation",
            "",
            "- Modest locust cycle should show ~0% 5xx; 429 failures mean we exceeded limits.",
            "- Onset attempt number ≈ requests before first 429 for one identity on POST /api/v1/orders.",
            "- Defaults: RATE_LIMIT=600/minute (global IP), RATE_LIMIT_MUTATING=600/minute (token+path).",
            "",
        ]
        out_md.write_text("\n".join(lines), encoding="utf-8")
        # Also write JSON for tooling
        (RESULTS / f"trade-{stamp}-onset.json").write_text(
            json.dumps(onset, indent=2, default=str) + "\n", encoding="utf-8"
        )
        _log(f"report → {out_md}")
        if five_xx_count > 0:
            _log(f"WARNING: observed 5xx markers in failures: {five_xx_count}")
            return 2
        return 0 if code == 0 else code
    finally:
        if stack_cm is not None:
            stack_cm.__exit__(None, None, None)


if __name__ == "__main__":
    raise SystemExit(main())
