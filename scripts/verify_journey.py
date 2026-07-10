#!/usr/bin/env python3
"""Verify the core AlphaEdge production journey.

Stdlib only. Runs entirely against production by default:

  py -3.13 scripts/verify_journey.py

Journey:
  browse markets -> open live market snapshot -> live candles -> AI analysis
  -> signup -> place authenticated paper order -> portfolio shows position.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_API = "https://mukeshkumar007-alphaedge-api.hf.space"
TIMEOUT = 35
RETRIES = 2
UA = "alphaedge-verify-journey/1.0"


class StepError(RuntimeError):
    pass


def _decode(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")


def _request(
    method: str,
    url: str,
    *,
    token: str | None = None,
    body: dict | None = None,
    timeout: int = TIMEOUT,
):
    headers = {
        "User-Agent": UA,
        "Accept": "application/json",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    last_exc: BaseException | None = None
    for attempt in range(RETRIES + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return resp.getcode(), _json_or_text(raw)
        except urllib.error.HTTPError as exc:
            raw = b""
            try:
                raw = exc.read()
            except Exception:
                pass
            payload = _json_or_text(raw)
            if exc.code in (429, 500, 502, 503, 504) and attempt < RETRIES:
                last_exc = exc
                time.sleep(2 + attempt)
                continue
            return exc.code, payload
        except (TimeoutError, OSError, urllib.error.URLError) as exc:
            last_exc = exc
            if attempt < RETRIES:
                time.sleep(2 + attempt)
                continue
            raise StepError(f"{method} {url} failed: {exc!r}") from exc
    raise StepError(f"{method} {url} failed: {last_exc!r}")


def _json_or_text(raw: bytes):
    text = _decode(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _get_json(url: str, *, token: str | None = None):
    return _request("GET", url, token=token)


def _post_json(url: str, *, token: str | None = None, body: dict | None = None, timeout: int = TIMEOUT):
    return _request("POST", url, token=token, body=body, timeout=timeout)


def _fail(message: str) -> None:
    raise StepError(message)


def _assert_status(name: str, status: int, payload, expected: int | tuple[int, ...] = 200) -> None:
    expected_codes = expected if isinstance(expected, tuple) else (expected,)
    if status not in expected_codes:
        detail = payload
        if isinstance(payload, dict) and "detail" in payload:
            detail = payload["detail"]
        _fail(f"{name}: HTTP {status}, expected {expected_codes}, body={detail!r}")


def _book_has_prices(snapshot: dict) -> bool:
    market = snapshot.get("market")
    if isinstance(market, dict):
        yes_price = _as_float(market.get("yes_price"))
        if yes_price is not None and 0.0 <= yes_price <= 1.0:
            return True
    book = snapshot.get("book")
    if not isinstance(book, dict):
        return False
    for side in ("yes", "no"):
        side_book = book.get(side)
        if not isinstance(side_book, dict):
            continue
        for levels_name in ("asks", "bids"):
            levels = side_book.get(levels_name)
            if not isinstance(levels, list):
                continue
            for level in levels:
                if isinstance(level, dict) and _as_float(level.get("price")) is not None:
                    return True
    return False


def _snapshot_price(snapshot: dict, fallback: float | None) -> float:
    market = snapshot.get("market") if isinstance(snapshot, dict) else None
    if isinstance(market, dict):
        yes_price = _as_float(market.get("yes_price"))
        if yes_price is not None and 0.01 <= yes_price <= 0.99:
            return yes_price
    book = snapshot.get("book") if isinstance(snapshot, dict) else None
    if isinstance(book, dict):
        yes = book.get("yes")
        if isinstance(yes, dict):
            for levels_name in ("asks", "bids"):
                levels = yes.get(levels_name)
                if isinstance(levels, list):
                    for level in levels:
                        if isinstance(level, dict):
                            price = _as_float(level.get("price"))
                            if price is not None and 0.01 <= price <= 0.99:
                                return price
    if fallback is not None and 0.01 <= fallback <= 0.99:
        return fallback
    return 0.5


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _position_matches(portfolio: dict, slug: str) -> bool:
    positions = portfolio.get("positions")
    if not isinstance(positions, list):
        return False
    for pos in positions:
        if not isinstance(pos, dict):
            continue
        shares = _as_float(pos.get("shares"))
        if pos.get("market_slug") == slug and shares is not None and shares > 0:
            return True
    return False


def _brief_has_rationale(brief: dict) -> bool:
    for key in ("rationale", "body_markdown", "headline"):
        value = brief.get(key)
        if isinstance(value, str) and len(value.strip()) >= 20:
            return True
    claim = brief.get("claim")
    return isinstance(claim, dict) and bool(claim.get("direction"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify production AlphaEdge core user journey.")
    parser.add_argument("--api", default=DEFAULT_API, help="Production API base URL")
    parser.add_argument("--max-market-probes", type=int, default=40)
    parser.add_argument(
        "--readonly",
        action="store_true",
        help=(
            "Skip signup + paper order (steps 4-5). Use for scheduled monitors so "
            "cron does not create junk accounts/orders every 30 minutes."
        ),
    )
    args = parser.parse_args()
    api = args.api.rstrip("/")

    results: list[tuple[str, bool, str]] = []
    state: dict[str, object] = {}

    def record(name: str, ok: bool, message: str) -> None:
        results.append((name, ok, message))
        print(f"{'PASS' if ok else 'FAIL'}  {name} - {message}")

    def step(name: str, fn) -> None:
        try:
            message = fn()
            record(name, True, message)
        except Exception as exc:  # noqa: BLE001 - verifier prints one-line failure
            record(name, False, str(exc))

    def browse_and_pick() -> str:
        status, data = _get_json(f"{api}/api/v1/markets")
        _assert_status("GET /api/v1/markets", status, data)
        if not isinstance(data, list):
            _fail("markets response is not a list")
        candidates = [
            item
            for item in data
            if isinstance(item, dict)
            and str(item.get("source", "")).lower() == "polymarket"
            and str(item.get("status", "")).lower() == "open"
            and str(item.get("slug", "")).startswith("pm-")
        ]
        if not candidates:
            _fail("no open source=polymarket pm-* markets returned")
        state["markets"] = candidates
        return f"{len(candidates)} open Polymarket markets available"

    def pick_live_market() -> str:
        candidates = state.get("markets")
        if not isinstance(candidates, list):
            _fail("market list missing from browse step")
        last_error = "not probed"
        for market in candidates[: max(args.max_market_probes, 1)]:
            if not isinstance(market, dict):
                continue
            slug = str(market.get("slug", ""))
            if not slug:
                continue

            snapshot_status, snapshot = _get_json(
                f"{api}/api/v1/markets/{urllib.parse.quote(slug)}/snapshot"
            )
            if snapshot_status != 200 or not isinstance(snapshot, dict) or not _book_has_prices(snapshot):
                last_error = f"{slug}: snapshot status={snapshot_status} prices={_book_has_prices(snapshot) if isinstance(snapshot, dict) else False}"
                continue

            candles_status, candles_payload = _get_json(
                f"{api}/api/v1/markets/{urllib.parse.quote(slug)}/candles?points=30"
            )
            candles = candles_payload.get("candles") if isinstance(candles_payload, dict) else None
            source = candles_payload.get("source") if isinstance(candles_payload, dict) else None
            if candles_status == 200 and source == "live" and isinstance(candles, list) and candles:
                state["market"] = market
                state["slug"] = slug
                state["snapshot"] = snapshot
                state["candles"] = candles_payload
                state["price"] = _snapshot_price(snapshot, _as_float(market.get("yes_price")))
                return f"slug={slug} snapshot prices ok; live candles={len(candles)}"
            last_error = f"{slug}: candles status={candles_status} source={source!r} count={len(candles) if isinstance(candles, list) else 'n/a'}"
        _fail(f"no candidate had both snapshot prices and live candles; last={last_error}")

    def analyst() -> str:
        slug = str(state.get("slug") or "")
        if not slug:
            _fail("slug missing from market step")
        token = str(state.get("token") or "")
        if not token:
            _fail("token missing before analyst step (H-SEC-03: analyst/run requires auth)")
        url = f"{api}/api/v1/analyst/run?{urllib.parse.urlencode({'market_slug': slug})}"
        status, brief = _post_json(url, token=token, timeout=75)
        _assert_status("POST /api/v1/analyst/run", status, brief)
        if not isinstance(brief, dict):
            _fail("analyst response is not an object")
        if not _brief_has_rationale(brief):
            _fail("analyst response lacks rationale/body/claim content")
        generator = str(brief.get("generator", ""))
        state["brief"] = brief
        warning = ""
        if generator == "fallback":
            warning = " WARNING: ANALYST GENERATOR IS FALLBACK; owner-managed LLM key may be absent."
        return f"brief={brief.get('id')} generator={generator}{warning}"

    def signup() -> str:
        nonce = f"{int(time.time())}-{secrets.token_hex(4)}"
        email = f"journey-{nonce}@example.com"
        password = "AlphaEdge!2345"
        status, token_payload = _post_json(
            f"{api}/api/v1/auth/signup",
            body={"email": email, "password": password},
        )
        _assert_status("POST /api/v1/auth/signup", status, token_payload, expected=201)
        if not isinstance(token_payload, dict) or not token_payload.get("access_token"):
            _fail("signup response did not include access_token")
        token = str(token_payload["access_token"])
        state["token"] = token
        state["email"] = email

        me_status, me = _get_json(f"{api}/api/v1/auth/me", token=token)
        _assert_status("GET /api/v1/auth/me", me_status, me)
        if not isinstance(me, dict) or me.get("email") != email:
            _fail(f"auth/me did not return created user email={email!r}")
        return f"created user={email} balance={me.get('paper_balance')}"

    def order_and_portfolio() -> str:
        token = str(state.get("token") or "")
        slug = str(state.get("slug") or "")
        if not token or not slug:
            _fail("token or slug missing before order step")
        price = _as_float(state.get("price"))
        if price is None:
            price = 0.5
        price = min(max(round(price, 4), 0.01), 0.99)
        shares = 1
        status, order = _post_json(
            f"{api}/api/v1/orders",
            token=token,
            body={
                "slug": slug,
                "side": "buy",
                "outcome": "yes",
                "shares": shares,
                "price": price,
            },
        )
        _assert_status("POST /api/v1/orders", status, order, expected=201)
        if not isinstance(order, dict) or order.get("slug") != slug or not order.get("paper_trading_only"):
            _fail(f"unexpected order payload={order!r}")
        state["order"] = order

        portfolio_status, portfolio = _get_json(f"{api}/api/v1/portfolio", token=token)
        _assert_status("GET /api/v1/portfolio", portfolio_status, portfolio)
        if not isinstance(portfolio, dict):
            _fail("portfolio response is not an object")
        if not portfolio.get("paper_trading_only"):
            _fail("portfolio did not confirm paper_trading_only")
        if not _position_matches(portfolio, slug):
            _fail(f"portfolio positions did not include slug={slug}")
        return f"order={order.get('order_id')} slug={slug} shares={shares} price={price}"

    step("1 browse markets", browse_and_pick)
    step("2 snapshot and live candles", pick_live_market)
    if args.readonly:
        # analyst/run requires a JWT (H-SEC-03) and writes a brief, so it is a
        # write step too — skipped alongside signup/order on the readonly cron.
        print("SKIP  3 AI analysis brief - --readonly (requires auth; writes a brief)")
        print("SKIP  4 signup user - --readonly (no junk accounts on cron)")
        print("SKIP  5 paper order and portfolio - --readonly (no junk orders on cron)")
    else:
        step("3 signup user", signup)
        step("4 AI analysis brief", analyst)
        step("5 paper order and portfolio", order_and_portfolio)

    slug = state.get("slug")
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    mode = "readonly" if args.readonly else "full"
    print(f"\nMARKET_SLUG={slug or 'n/a'}")
    print(f"RESULT: {passed}/{total} journey steps passed (mode={mode})")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
