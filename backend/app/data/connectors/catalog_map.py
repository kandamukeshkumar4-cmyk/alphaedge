from dataclasses import dataclass
from typing import Literal

SourceKind = Literal["polymarket", "kalshi", "seed"]


@dataclass(frozen=True)
class CatalogEntry:
    slug: str
    source: SourceKind
    external_slug: str | None = None
    spec_price: float = 0.5


CATALOG_MAP: dict[str, CatalogEntry] = {
    "nba-2025-01-15-lal-bos": CatalogEntry(
        "nba-2025-01-15-lal-bos", "seed", spec_price=0.65
    ),
    "nba-warriors-playoff-seed": CatalogEntry(
        "nba-warriors-playoff-seed", "seed", spec_price=0.58
    ),
    "elect-la-mayor-2026": CatalogEntry(
        "elect-la-mayor-2026", "seed", spec_price=0.66
    ),
    "elect-2028-dem-nominee": CatalogEntry(
        "elect-2028-dem-nominee", "seed", spec_price=0.23
    ),
    "wc2026-m1-mex-homewin": CatalogEntry("wc2026-m1-mex-homewin", "seed", spec_price=0.44),
    "wc2026-m1-draw": CatalogEntry("wc2026-m1-draw", "seed", spec_price=0.27),
    "wc2026-m1-rsa-awaywin": CatalogEntry(
        "wc2026-m1-rsa-awaywin", "seed", spec_price=0.29
    ),
    "wc2026-winner-brazil": CatalogEntry(
        "wc2026-winner-brazil", "seed", spec_price=0.16
    ),
    "wc2026-winner-france": CatalogEntry(
        "wc2026-winner-france", "seed", spec_price=0.15
    ),
    "wc2026-winner-argentina": CatalogEntry(
        "wc2026-winner-argentina", "seed", spec_price=0.19
    ),
    "crypto-btc-friday-5pm": CatalogEntry(
        "crypto-btc-friday-5pm",
        "polymarket",
        "will-btc-be-above-70000-on",
        spec_price=0.42,
    ),
    "crypto-eth-100k-eoy": CatalogEntry(
        "crypto-eth-100k-eoy", "seed", spec_price=0.55
    ),
    "culture-gta6-trailer": CatalogEntry(
        "culture-gta6-trailer", "seed", spec_price=0.74
    ),
    "culture-love-island-elim": CatalogEntry(
        "culture-love-island-elim", "seed", spec_price=0.27
    ),
    "econ-cpi-above-3": CatalogEntry("econ-cpi-above-3", "seed", spec_price=0.40),
    "econ-fed-cut-march": CatalogEntry("econ-fed-cut-march", "seed", spec_price=0.31),
}
