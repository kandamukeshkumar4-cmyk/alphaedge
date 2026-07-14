#!/usr/bin/env python3
"""Boot an isolated local uvicorn for Loop V20 load tests.

Pattern: A6/E5 / Loop V17 e2e — isolated SQLite + PAPER_TRADING_ONLY +
schedulers off. NEVER talks to Railway/Vercel.

Usage:
  py -3.13 loadtest/scripts/boot_local_stack.py            # foreground, stay up
  py -3.13 loadtest/scripts/boot_local_stack.py --check    # boot, health, exit 0
  py -3.13 loadtest/scripts/boot_local_stack.py --port 18020

Env:
  LOADTEST_API_PORT   default 18020
  LOADTEST_KEEP_DB    if 1, reuse existing sqlite file
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
LOADTEST_DIR = REPO_ROOT / "loadtest"
DATA_DIR = LOADTEST_DIR / ".data"
LOG_DIR = DATA_DIR / "logs"
DB_PATH = DATA_DIR / "loop20.sqlite3"
INIT_SCRIPT = LOADTEST_DIR / "scripts" / "init_sqlite_db.py"

DEFAULT_PORT = int(os.environ.get("LOADTEST_API_PORT", "18020"))


def _log(msg: str) -> None:
    print(f"[loop20-stack] {msg}", flush=True)


def _sqlite_urls(db_path: Path) -> tuple[str, str]:
    # Windows-friendly absolute SQLite URL (forward slashes).
    db_url_path = str(db_path.resolve()).replace("\\", "/")
    return (
        f"sqlite+aiosqlite:///{db_url_path}",
        f"sqlite:///{db_url_path}",
    )


def backend_env(port: int) -> dict[str, str]:
    database_url, database_url_sync = _sqlite_urls(DB_PATH)
    env = os.environ.copy()
    env.update(
        {
            "PAPER_TRADING_ONLY": "true",
            "DATABASE_URL": database_url,
            "DATABASE_URL_SYNC": database_url_sync,
            "REDIS_URL": "redis://disabled",
            "APP_ENV": "development",
            "ADMIN_API_KEY": "dev-admin-key",
            "JWT_SECRET_KEY": "loop20-load-jwt-secret",
            "CORS_ORIGINS": f"http://127.0.0.1:{port},http://localhost:{port}",
            "LIVE_FEED_ENABLED": "false",
            "SCHEDULER_NEWS_SCAN_ENABLED": "false",
            "SCHEDULER_NEWS_MISPRICING_ENABLED": "false",
            "SCHEDULER_UNUSUAL_FLOW_ENABLED": "false",
            "SCHEDULER_WEATHER_SCAN_ENABLED": "false",
            "SCHEDULER_MORNING_RESEARCH_ENABLED": "false",
            "SCHEDULER_WHALE_REFRESH_ENABLED": "false",
            "SCHEDULER_WC2026_RESOLVE_ENABLED": "false",
            "SCHEDULER_EXTERNAL_RESOLVE_ENABLED": "false",
            "SCHEDULER_EXTERNAL_AUTOLOCK_ENABLED": "false",
            "PYTHONUNBUFFERED": "1",
            # Keep default mutating limit; L3 documents 429 onset — do not disable.
            "RATE_LIMIT_MUTATING_ENABLED": "true",
        }
    )
    return env


def _quote(path: Path) -> str:
    return f'"{str(path).replace(chr(34), chr(92) + chr(34))}"'


def init_sqlite(env: dict[str, str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    keep = os.environ.get("LOADTEST_KEEP_DB", "").strip() in {"1", "true", "yes"}
    if DB_PATH.exists() and not keep:
        DB_PATH.unlink()
        _log(f"removed previous db {DB_PATH}")
    _log(f"init sqlite schema at {DB_PATH}")
    # Prefer uv run so worktree venv + aiosqlite extra are used.
    uv = shutil.which("uv")
    if uv:
        cmd = f'uv run --extra dev python {_quote(INIT_SCRIPT)}'
    else:
        cmd = f'{sys.executable} {_quote(INIT_SCRIPT)}'
    proc = subprocess.run(
        cmd,
        cwd=str(BACKEND_DIR),
        env=env,
        shell=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"init_sqlite_db.py exited {proc.returncode}")


def start_uvicorn(port: int, env: dict[str, str]) -> subprocess.Popen:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "uvicorn.log"
    _log(f"starting uvicorn on 127.0.0.1:{port} (log={log_path})")
    uv = shutil.which("uv")
    if uv:
        cmd = (
            f"uv run --extra dev uvicorn app.main:app "
            f"--host 127.0.0.1 --port {port} --log-level warning"
        )
    else:
        cmd = (
            f"{sys.executable} -m uvicorn app.main:app "
            f"--host 127.0.0.1 --port {port} --log-level warning"
        )
    log_f = open(log_path, "a", encoding="utf-8")
    # shell=True on Windows is the reliable spawn path (same as e2e helper).
    child = subprocess.Popen(
        cmd,
        cwd=str(BACKEND_DIR),
        env=env,
        shell=True,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )
    child._loop20_log = log_f  # type: ignore[attr-defined]
    return child


def wait_for_health(port: int, timeout_s: float = 90.0) -> dict:
    url = f"http://127.0.0.1:{port}/health"
    start = time.time()
    last_err = ""
    while time.time() - start < timeout_s:
        try:
            with urllib.request.urlopen(url, timeout=2.5) as resp:
                body = resp.read().decode("utf-8")
                data = json.loads(body)
                if resp.status == 200:
                    return data
                last_err = f"HTTP {resp.status}"
        except Exception as exc:  # noqa: BLE001 — boot wait
            last_err = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"Timeout waiting for {url}: {last_err}")


def assert_local_ready(port: int) -> dict:
    health = wait_for_health(port)
    if health.get("paper_trading_only") is not True:
        raise RuntimeError(
            f"backend health missing paper_trading_only=true: {health!r}"
        )
    markets_url = f"http://127.0.0.1:{port}/api/v1/markets"
    with urllib.request.urlopen(markets_url, timeout=10) as resp:
        markets = json.loads(resp.read().decode("utf-8"))
    count = len(markets) if isinstance(markets, list) else len(markets.get("items") or [])
    _log(f"health ok paper_trading_only={health.get('paper_trading_only')} markets≈{count}")
    return {"health": health, "markets_count": count, "base_url": f"http://127.0.0.1:{port}"}


def stop_child(child: subprocess.Popen | None) -> None:
    if child is None:
        return
    if child.poll() is not None:
        return
    _log(f"stopping uvicorn pid={child.pid}")
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                capture_output=True,
                check=False,
            )
        else:
            child.send_signal(signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
    except Exception as exc:  # noqa: BLE001
        _log(f"stop warning: {exc}")
    log_f = getattr(child, "_loop20_log", None)
    if log_f is not None:
        try:
            log_f.close()
        except Exception:
            pass


class LocalStack:
    """Context manager: boot stack, yield base_url, tear down."""

    def __init__(self, port: int = DEFAULT_PORT, check_only: bool = False):
        self.port = port
        self.check_only = check_only
        self.child: subprocess.Popen | None = None
        self.base_url = f"http://127.0.0.1:{port}"
        self.info: dict = {}

    def __enter__(self) -> "LocalStack":
        env = backend_env(self.port)
        init_sqlite(env)
        self.child = start_uvicorn(self.port, env)
        try:
            self.info = assert_local_ready(self.port)
            self.base_url = self.info["base_url"]
        except Exception:
            stop_child(self.child)
            self.child = None
            raise
        # Write a small ready file for external runners.
        ready_path = DATA_DIR / "ready.json"
        ready_path.write_text(
            json.dumps(
                {
                    "base_url": self.base_url,
                    "port": self.port,
                    "pid": self.child.pid if self.child else None,
                    "paper_trading_only": True,
                    "markets_count": self.info.get("markets_count"),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        _log(f"stack ready api={self.base_url}")
        return self

    def __exit__(self, *exc) -> None:
        stop_child(self.child)
        self.child = None
        ready = DATA_DIR / "ready.json"
        if ready.exists():
            try:
                ready.unlink()
            except OSError:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Boot Loop V20 local API stack")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Boot, verify health+markets, shut down, exit 0/1",
    )
    parser.add_argument(
        "--ready-file",
        type=Path,
        default=DATA_DIR / "ready.json",
        help="Write readiness JSON here while stack is up",
    )
    args = parser.parse_args(argv)

    # Safety: only bind loopback.
    if args.port < 1 or args.port > 65535:
        _log(f"invalid port {args.port}")
        return 2

    stack = LocalStack(port=args.port, check_only=args.check)
    try:
        with stack:
            if args.check:
                _log("check mode: stack healthy, shutting down")
                return 0
            _log("foreground mode: Ctrl+C to stop")
            # Stay alive until signal.
            while True:
                if stack.child and stack.child.poll() is not None:
                    _log(f"uvicorn exited early code={stack.child.returncode}")
                    return stack.child.returncode or 1
                time.sleep(1)
    except KeyboardInterrupt:
        _log("interrupted")
        return 0
    except Exception as exc:
        _log(f"FATAL: {exc}")
        return 1


def main_cli() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    raise SystemExit(main())
