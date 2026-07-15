"""D1 read-only audit of prod markets + signals dumps."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

base = Path(__file__).resolve().parent
markets = json.loads((base / "_prod_markets.json").read_text(encoding="utf-8"))
signals = json.loads((base / "_prod_signals.json").read_text(encoding="utf-8"))

print("MARKETS", len(markets))
print("market keys", sorted(markets[0].keys()))
print(
    "sample",
    {
        k: markets[0].get(k)
        for k in ["slug", "title", "status", "category", "lock_at", "yes_price", "source"]
    },
)

status_c = Counter((m.get("status") or "").lower() for m in markets)
print("status", dict(status_c))
cat_c = Counter((m.get("category") or "") for m in markets)
print("categories", cat_c.most_common(40))
print("unique categories", len(cat_c))

open_m = [m for m in markets if (m.get("status") or "").lower() == "open"]
print("open count", len(open_m))

now = datetime.now(timezone.utc)


def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


stale = []
for m in open_m:
    lock = parse_dt(m.get("lock_at"))
    close = parse_dt(m.get("close_at")) if m.get("close_at") else None
    ref = close or lock
    if ref and ref < now:
        stale.append(
            {
                "slug": m.get("slug"),
                "title": m.get("title"),
                "ref": ref.isoformat(),
                "yes_price": m.get("yes_price"),
                "category": m.get("category"),
                "source": m.get("source"),
            }
        )

print("stale open past lock/close", len(stale))
for row in sorted(stale, key=lambda r: r["ref"])[:30]:
    print("  STALE", row)

decided_open = [
    m
    for m in open_m
    if m.get("yes_price") is not None
    and (float(m["yes_price"]) <= 0.01 or float(m["yes_price"]) >= 0.99)
]
print("open with extreme price", len(decided_open))
for m in decided_open[:20]:
    print(
        "  DEC",
        m.get("slug"),
        str(m.get("title"))[:80],
        m.get("yes_price"),
        m.get("lock_at"),
    )

title_map: dict[str, list] = defaultdict(list)
for m in markets:
    title_map[(m.get("title") or "").strip()].append(m)

dup_titles = {t: ms for t, ms in title_map.items() if t and len(ms) > 1}
print(
    "duplicate title groups",
    len(dup_titles),
    "markets in dups",
    sum(len(v) for v in dup_titles.values()),
)
for t, ms in sorted(dup_titles.items(), key=lambda kv: -len(kv[1]))[:25]:
    print(f"  TITLE x{len(ms)}: {t[:120]!r}")
    for m in ms[:8]:
        print(
            f"     {m.get('slug')} status={m.get('status')} yes={m.get('yes_price')} "
            f"cat={m.get('category')} src={m.get('source')}"
        )


def family(slug: str) -> str:
    s = slug or ""
    s = re.sub(r":yes$", "", s)
    s = re.sub(r"-\d{2,}$", "", s)
    if s.startswith("kalshi:"):
        body = s.split(":", 1)[1]
        body = re.sub(r"-\d+$", "", body)
        # series: strip trailing outcome token after last hyphen group if long
        return "kalshi:" + body
    if s.startswith("pm-"):
        return re.sub(r"-\d+$", "", s)
    return s


fam_map: dict[str, list] = defaultdict(list)
for m in markets:
    fam_map[family(m.get("slug") or "")].append(m)
multi_fam = {f: ms for f, ms in fam_map.items() if len(ms) > 1}
print(
    "slug family multi",
    len(multi_fam),
    "markets",
    sum(len(v) for v in multi_fam.values()),
)
for f, ms in sorted(multi_fam.items(), key=lambda kv: -len(kv[1]))[:20]:
    titles = {m.get("title") for m in ms}
    print(f"  FAM x{len(ms)} {f[:100]} unique_titles={len(titles)}")
    for m in ms[:6]:
        print(
            f"     {m.get('slug')} | {str(m.get('title'))[:70]} | "
            f"{m.get('status')} | {m.get('yes_price')}"
        )

identical_open = {
    t: [m for m in ms if (m.get("status") or "").lower() == "open"]
    for t, ms in dup_titles.items()
}
identical_open = {t: ms for t, ms in identical_open.items() if len(ms) > 1}
print("OPEN identical title groups", len(identical_open))
for t, ms in sorted(identical_open.items(), key=lambda kv: -len(kv[1]))[:20]:
    print(f"  OPEN TITLE x{len(ms)}: {t[:120]!r}")
    for m in ms[:10]:
        print(
            f"     {m.get('slug')} yes={m.get('yes_price')} src={m.get('source')} "
            f"lock={m.get('lock_at')}"
        )

print("\n=== CATEGORY BREAKDOWN open/total ===")
for cat, total in sorted(cat_c.items(), key=lambda kv: -kv[1]):
    open_n = sum(
        1
        for m in markets
        if m.get("category") == cat and (m.get("status") or "").lower() == "open"
    )
    print(f"  {cat!r}: total={total} open={open_n}")

# category taxonomy mismatch helpers
sports_cats = {"NBA", "NFL", "FIFA WC2026", "sports", "Sports"}
sports_total = sum(1 for m in markets if m.get("category") in sports_cats or (m.get("slug") or "").startswith("wc2026-"))
sports_open = sum(
    1
    for m in markets
    if (m.get("category") in sports_cats or (m.get("slug") or "").startswith("wc2026-"))
    and (m.get("status") or "").lower() == "open"
)
print(f"sports taxonomy total={sports_total} open={sports_open}")

# category summaries on disk
for name in ["sports", "politics", "crypto"]:
    p = base / f"_prod-api-v1-categories-{name}-summary.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        print(
            f"summary {name}: market_count={d.get('market_count')} "
            f"found={d.get('found')} recent_signals={d.get('recent_signal_count')}"
        )

print("\n=== SIGNALS ===")
if isinstance(signals, dict):
    print("signals keys", list(signals.keys()))
    sig_rows = signals.get("items") or []
else:
    sig_rows = signals if isinstance(signals, list) else []
print("signal rows", len(sig_rows))
if sig_rows:
    print("sig keys", sorted(sig_rows[0].keys()))
    market_ids = [s.get("market_id") for s in sig_rows]
    slugs = {m.get("slug") for m in markets}
    orphan = [mid for mid in market_ids if mid and mid not in slugs]
    present = [mid for mid in market_ids if mid and mid in slugs]
    null_title = [s for s in sig_rows if not s.get("market_title")]
    print("orphan signal market_ids", len(orphan), "of", len(market_ids))
    print("matched", len(present), "null_title", len(null_title))
    print("unique orphan", len(set(orphan)))
    for mid, c in Counter(orphan).most_common(20):
        print(f"  ORPHAN x{c}: {mid}")
    for s in sig_rows[:5]:
        print(
            " sample",
            {
                "market_id": s.get("market_id"),
                "market_title": s.get("market_title"),
                "signal_type": s.get("signal_type"),
                "platform": s.get("platform"),
                "created_at": s.get("created_at"),
            },
        )
    # orphan by platform
    orphan_set = set(orphan)
    print(
        "orphan platforms",
        Counter(s.get("platform") for s in sig_rows if s.get("market_id") in orphan_set),
    )
    print(
        "orphan types",
        Counter(s.get("signal_type") for s in sig_rows if s.get("market_id") in orphan_set),
    )

# Write compact summary json for STATE
report = {
    "audited_at": now.isoformat(),
    "market_count": len(markets),
    "status_counts": dict(status_c),
    "category_counts": dict(cat_c),
    "open_count": len(open_m),
    "stale_open_count": len(stale),
    "stale_open_examples": sorted(stale, key=lambda r: r["ref"])[:15],
    "extreme_price_open_count": len(decided_open),
    "duplicate_title_groups": len(dup_titles),
    "duplicate_title_markets": sum(len(v) for v in dup_titles.values()),
    "open_identical_title_groups": len(identical_open),
    "open_identical_title_examples": [
        {
            "title": t,
            "count": len(ms),
            "slugs": [m.get("slug") for m in ms[:8]],
            "sources": list({m.get("source") for m in ms}),
        }
        for t, ms in sorted(identical_open.items(), key=lambda kv: -len(kv[1]))[:15]
    ],
    "slug_family_multi_count": len(multi_fam),
    "sports_summary_market_count": None,
    "signal_sample_size": len(sig_rows),
    "orphan_signal_count_in_sample": len(orphan) if sig_rows else 0,
    "orphan_unique": len(set(orphan)) if sig_rows else 0,
    "orphan_examples": Counter(orphan).most_common(15) if sig_rows else [],
}
for name in ["sports", "politics", "crypto"]:
    p = base / f"_prod-api-v1-categories-{name}-summary.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        report[f"{name}_summary_market_count"] = d.get("market_count")
        report[f"{name}_summary_recent_signals"] = d.get("recent_signal_count")

(base / "_d1_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("\nWrote", base / "_d1_report.json")
