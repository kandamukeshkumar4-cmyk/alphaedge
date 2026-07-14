#!/usr/bin/env python3
"""Production verifier for the AlphaEdge e2e ship.

Stdlib only (urllib + json). Checks PRODUCTION and exits nonzero on any
failure, printing PASS/FAIL per check. Run:  py -3.13 scripts/verify_prod.py

  1. GET {api}/health                 -> 200, status ok
  2. GET {api}/api/v1/markets?limit=300 -> >=200 open+locked, >=100 polymarket, >=5 kalshi
  3. one open polymarket market candles -> non-empty candles, source "live"
  4. GET {api}/api/v1/signals?limit=5  -> >=1 signal
  5. GET frontend homepage (+JS chunks) -> >=3 "pm-" slugs that are a valid
     open/active SUBSET of GET /api/v1/markets (full listing); no "alpha_quant"
  6. GET {api}/api/v1/memories?limit=1  -> 200
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_API = "https://mukeshkumar007-alphaedge-api.hf.space"
DEFAULT_FRONTEND = "https://alphaedge-frontend-three.vercel.app"
TIMEOUT = 25
RETRIES = 2
MAX_CHUNKS = 15
UA = "alphaedge-verify-prod/1.0"


def http_get(url: str, retries: int = RETRIES, timeout: int = TIMEOUT):
    """Return (status, body_bytes). Retry 429/5xx/conn errors once. Raise on hard conn failure."""
    last_exc = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            url,
            headers={"User-Agent": UA, "Accept": "application/json, text/html, */*"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.getcode(), resp.read()
        except urllib.error.HTTPError as e:
            body = b""
            try:
                body = e.read()
            except Exception:
                pass
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                last_exc = e
                time.sleep(2)
                continue
            return e.code, body
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_exc = e
            if attempt < retries:
                time.sleep(2)
                continue
            raise
    raise last_exc  # type: ignore[misc]


def _decode(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")


def _get_json(url: str):
    status, body = http_get(url)
    try:
        data = json.loads(_decode(body))
    except json.JSONDecodeError:
        data = None
    return status, data, body


_PM_SLUG_RE = re.compile(r"pm-[a-z0-9][a-z0-9-]+")
_ACTIVE_STATUSES = frozenset({"open", "locked"})


def extract_pm_slugs(text: str) -> set[str]:
    """Unique pm- slugs embedded in SSR HTML / JS chunks."""
    return set(_PM_SLUG_RE.findall(text))


def catalog_pm_slug_set(markets: list) -> set[str]:
    """All pm- slugs from a full /markets listing (any status)."""
    out: set[str] = set()
    for m in markets:
        slug = m.get("slug")
        if isinstance(slug, str) and slug.startswith("pm-"):
            out.add(slug)
    return out


def active_pm_slug_set(markets: list) -> set[str]:
    """pm- slugs from a full /markets listing that are open or locked (active)."""
    out: set[str] = set()
    for m in markets:
        slug = m.get("slug")
        if not isinstance(slug, str) or not slug.startswith("pm-"):
            continue
        if str(m.get("status", "")).lower() in _ACTIVE_STATUSES:
            out.add(slug)
    return out


def homepage_subset_ok(
    homepage_slugs: set[str],
    active_api_slugs: set[str],
    catalog_pm_count: int,
    *,
    floor: int = 3,
) -> tuple[bool, str]:
    """Assert homepage pm- slugs are an open/active subset of the API catalog.

    Returns (ok, detail) suitable for the check-5 message body (counts only;
    caller appends alpha_quant / chunk context). Denominator is total catalog
    pm- slugs (honest coverage: e.g. "156 homepage slugs, all valid subset of 586").
    """
    n_home = len(homepage_slugs)
    if n_home < floor:
        return (
            False,
            f"{n_home} homepage slugs (need >={floor}); catalog pm-={catalog_pm_count}",
        )
    invalid = sorted(homepage_slugs - active_api_slugs)
    if invalid:
        sample = ", ".join(invalid[:5])
        more = f" (+{len(invalid) - 5} more)" if len(invalid) > 5 else ""
        return (
            False,
            f"{n_home} homepage slugs, {len(invalid)} not open/active in API "
            f"(catalog pm-={catalog_pm_count}): {sample}{more}",
        )
    return True, f"{n_home} homepage slugs, all valid subset of {catalog_pm_count}"


def main() -> int:
    ap = argparse.ArgumentParser(description="AlphaEdge production verifier.")
    ap.add_argument("--api", default=DEFAULT_API, help="Backend API base URL")
    ap.add_argument("--frontend", default=DEFAULT_FRONTEND, help="Frontend base URL")
    args = ap.parse_args()
    api = args.api.rstrip("/")
    fe = args.frontend.rstrip("/")

    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, msg: str) -> None:
        results.append((name, ok, msg))
        print(f"{'PASS' if ok else 'FAIL'}  {name} — {msg}")

    # ---- Check 1: health ----
    try:
        status, data, _ = _get_json(f"{api}/health")
        ok = status == 200 and isinstance(data, dict) and data.get("status") == "ok"
        record("1 health", ok, f"status={status} body={data}")
    except Exception as e:  # noqa: BLE001
        record("1 health", False, f"error={e!r}")

    # ---- Check 2: markets catalog ----
    markets = None
    try:
        status, data, _ = _get_json(f"{api}/api/v1/markets?limit=300")
        markets = data if isinstance(data, list) else None
        if status != 200 or markets is None:
            record("2 markets", False, f"status={status} list={markets is None}")
        else:
            open_locked = sum(
                1 for m in markets if str(m.get("status", "")).lower() in ("open", "locked")
            )
            src = lambda s: str(s or "").lower()
            n_pm = sum(1 for m in markets if src(m.get("source")) == "polymarket")
            n_kal = sum(1 for m in markets if src(m.get("source")) == "kalshi")
            ok = open_locked >= 200 and n_pm >= 100 and n_kal >= 5
            record(
                "2 markets",
                ok,
                f"total={len(markets)} open+locked={open_locked} polymarket={n_pm} kalshi={n_kal}",
            )
    except Exception as e:  # noqa: BLE001
        record("2 markets", False, f"error={e!r}")

    # ---- Check 3: live candles for one open polymarket market ----
    try:
        if not markets:
            record("3 candles", False, "no markets from check 2")
        else:
            pm_open = [
                m["slug"]
                for m in markets
                if str(m.get("status", "")).lower() == "open"
                and str(m.get("source", "")).lower() == "polymarket"
                and m.get("slug")
            ]
            found_live = None
            last_probe = ""
            for slug in pm_open[:25]:
                status, data, _ = _get_json(f"{api}/api/v1/markets/{slug}/candles")
                last_probe = f"{slug} status={status}"
                if status == 200 and isinstance(data, dict):
                    candles = data.get("candles")
                    if isinstance(candles, list) and len(candles) > 0 and data.get("source") == "live":
                        found_live = slug
                        break
            if found_live:
                record("3 candles", True, f"live candles for {found_live} (probed {last_probe})")
            else:
                record("3 candles", False, f"no live candles among probed polymarket markets (last {last_probe})")
    except Exception as e:  # noqa: BLE001
        record("3 candles", False, f"error={e!r}")

    # ---- Check 4: signals ----
    try:
        status, data, _ = _get_json(f"{api}/api/v1/signals?limit=5")
        sigs = data.get("signals") if isinstance(data, dict) else None
        ok = status == 200 and isinstance(sigs, list) and len(sigs) >= 1
        record("4 signals", ok, f"status={status} count={len(sigs) if isinstance(sigs, list) else 'n/a'}")
    except Exception as e:  # noqa: BLE001
        record("4 signals", False, f"error={e!r}")

    # ---- Check 5: homepage pm- slugs are an open/active SUBSET of full /markets ----
    # Post loop16 V1 the SSR homepage is intentionally a trending/active subset,
    # not the full catalog — assert subset semantics, not full-catalog coverage.
    try:
        # Full listing (no limit) — do not reuse check-2's limit=300 URL.
        mstatus, mdata, _ = _get_json(f"{api}/api/v1/markets")
        if mstatus != 200 or not isinstance(mdata, list):
            record(
                "5 frontend-live",
                False,
                f"full /markets listing unavailable status={mstatus}",
            )
        else:
            active_api = active_pm_slug_set(mdata)
            catalog_pm = catalog_pm_slug_set(mdata)
            status, body = http_get(f"{fe}/")
            html = _decode(body)

            # collect script srcs and fetch JS chunks (SSR + baked chunk payload)
            srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
            chunk_text = ""
            fetched = 0
            for src in srcs:
                if fetched >= MAX_CHUNKS:
                    break
                url = urllib.parse.urljoin(fe + "/", src)
                try:
                    cstatus, cbody = http_get(url, retries=1, timeout=TIMEOUT)
                    if cstatus == 200:
                        chunk_text += "\n" + _decode(cbody)
                        fetched += 1
                except Exception:
                    continue
            combined = html + "\n" + chunk_text
            homepage_slugs = extract_pm_slugs(combined)

            subset_ok, subset_msg = homepage_subset_ok(
                homepage_slugs, active_api, len(catalog_pm)
            )
            alpha_present = "alpha_quant" in combined
            ok = subset_ok and not alpha_present
            if alpha_present:
                msg = f"fake trades marker 'alpha_quant' present; {subset_msg}"
            else:
                msg = f"{subset_msg} (HTML+{fetched} chunks); no alpha_quant"
            record("5 frontend-live", ok, msg)
    except Exception as e:  # noqa: BLE001
        record("5 frontend-live", False, f"error={e!r}")

    # ---- Check 6: memories ----
    try:
        status, data, _ = _get_json(f"{api}/api/v1/memories?limit=1")
        ok = status == 200 and isinstance(data, dict)
        record("6 memories", ok, f"status={status}")
    except Exception as e:  # noqa: BLE001
        record("6 memories", False, f"error={e!r}")

    # ---- summary ----
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\nRESULT: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
