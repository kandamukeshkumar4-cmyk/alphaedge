"""Record raw WebSocket frames for offline parser tests.

Usage (from backend/):
  uv run --extra dev python scripts/record_ws_fixtures.py \\
    --source kalshi --ticker KXWCGAME-USA-BRA --max-frames 30 \\
    --out tests/fixtures/ws/kalshi_sample.jsonl

Read-only public endpoints — no API keys. Network required.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data.streams.kalshi_ws import DEFAULT_KALSHI_WS_URL  # noqa: E402

KALSHI_WS_URL = DEFAULT_KALSHI_WS_URL
POLYMARKET_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


def fixture_line(*, source: str, raw: str, recorded_at: datetime | None = None) -> str:
    """One JSONL record — pure so tests need no network."""
    ts = recorded_at or datetime.now(tz=UTC)
    return json.dumps(
        {"source": source, "recorded_at": ts.isoformat(), "raw": raw},
        ensure_ascii=False,
    )


def kalshi_subscribe_frame(tickers: list[str]) -> str:
    return json.dumps(
        {
            "id": 1,
            "cmd": "subscribe",
            "params": {
                "channels": ["ticker_v2", "orderbook_delta"],
                "market_tickers": sorted(tickers),
            },
        }
    )


def polymarket_subscribe_frame(asset_ids: list[str]) -> str:
    return json.dumps(
        {
            "type": "market",
            "assets_ids": asset_ids,
        }
    )


async def record_frames(
    *,
    source: str,
    ws_url: str,
    subscribe_payload: str,
    max_frames: int,
    timeout_sec: float,
) -> list[str]:
    import websockets

    loop = asyncio.get_running_loop()
    lines: list[str] = []
    deadline = loop.time() + timeout_sec
    async with websockets.connect(ws_url, open_timeout=15) as ws:
        await ws.send(subscribe_payload)
        while len(lines) < max_frames and loop.time() < deadline:
            try:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 10.0))
            except TimeoutError:
                break
            if not isinstance(raw, str):
                raw = raw.decode("utf-8", errors="replace")
            lines.append(fixture_line(source=source, raw=raw))
    return lines


async def main_async(args: argparse.Namespace) -> int:
    if args.source == "kalshi":
        if not args.ticker:
            print("kalshi requires at least one --ticker", file=sys.stderr)
            return 2
        ws_url = args.ws_url or KALSHI_WS_URL
        subscribe = kalshi_subscribe_frame(args.ticker)
        source = "kalshi"
    elif args.source == "polymarket":
        if not args.asset_id:
            print("polymarket requires at least one --asset-id", file=sys.stderr)
            return 2
        ws_url = args.ws_url or POLYMARKET_WS_URL
        subscribe = polymarket_subscribe_frame(args.asset_id)
        source = "polymarket"
    else:
        print(f"unknown source: {args.source}", file=sys.stderr)
        return 2

    print(f"connecting {ws_url} ({source}), max_frames={args.max_frames}")
    lines = await record_frames(
        source=source,
        ws_url=ws_url,
        subscribe_payload=subscribe,
        max_frames=args.max_frames,
        timeout_sec=args.timeout_sec,
    )
    if not lines:
        print("FAIL: no frames received", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} frames -> {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Record WS frames to JSONL fixtures")
    parser.add_argument("--source", choices=["kalshi", "polymarket"], required=True)
    parser.add_argument("--ticker", action="append", default=[], help="Kalshi market ticker")
    parser.add_argument("--asset-id", action="append", default=[], help="Polymarket CLOB asset id")
    parser.add_argument("--ws-url", default=None, help="Override WebSocket URL")
    parser.add_argument("--max-frames", type=int, default=30)
    parser.add_argument("--timeout-sec", type=float, default=60.0)
    parser.add_argument(
        "--out",
        required=True,
        help="Output JSONL path (e.g. tests/fixtures/ws/kalshi_sample.jsonl)",
    )
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
