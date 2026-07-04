"""U08 — Per-category model router (config-driven).

Maps market categories (slugs, tags, or explicit category labels) to named
pipeline configurations. When ENSEMBLE_ENABLED=False the router is still
importable but always returns the "single" pipeline (baseline unchanged).

Router configuration lives entirely in Settings (ensemble_router_config),
expressed as a JSON-serialisable dict. Example env value:

    ENSEMBLE_ROUTER_CONFIG={"NBA":"ensemble-v2","Elections":"single","default":"single"}

Key rules:
- "default" key is always consulted as the fallback when no category matches.
- Unknown categories fall back to "default" (never raise).
- ENSEMBLE_ENABLED=False forces "single" for every input regardless of config.
- No order-path imports here.
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Pipeline names the router can return.
# Only "single" is actually executed when ENSEMBLE_ENABLED=False.
PIPELINE_SINGLE = "single"
PIPELINE_ENSEMBLE_V2 = "ensemble-v2"

KNOWN_PIPELINES = frozenset({PIPELINE_SINGLE, PIPELINE_ENSEMBLE_V2})

# Default config (used when no env override is set).
# Conservative: everything routes to single-model until the AutoLab gate passes.
_DEFAULT_ROUTER_CONFIG: dict[str, str] = {
    "NBA": PIPELINE_SINGLE,
    "Elections": PIPELINE_SINGLE,
    "Sports": PIPELINE_SINGLE,
    "FIFA": PIPELINE_SINGLE,
    "Crypto": PIPELINE_SINGLE,
    "default": PIPELINE_SINGLE,
}


def parse_router_config(raw: str | None) -> dict[str, str]:
    """Parse a JSON string into a category->pipeline mapping.

    Falls back to _DEFAULT_ROUTER_CONFIG on any parse error so the
    application never crashes on a bad env value.
    """
    if not raw or not raw.strip():
        return dict(_DEFAULT_ROUTER_CONFIG)
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("must be a JSON object")
        validated: dict[str, str] = {}
        for k, v in parsed.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise ValueError("all keys and values must be strings")
            validated[k] = v
        if "default" not in validated:
            validated["default"] = PIPELINE_SINGLE
        return validated
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to parse ENSEMBLE_ROUTER_CONFIG: %s — using defaults", exc)
        return dict(_DEFAULT_ROUTER_CONFIG)


class ModelRouter:
    """Selects a pipeline name for a given market category.

    Parameters
    ----------
    config:
        Category-to-pipeline mapping. Must contain a "default" key.
    ensemble_enabled:
        Global ensemble flag. When False, all selections return PIPELINE_SINGLE
        regardless of the config, preserving the baseline.
    """

    def __init__(
        self,
        config: dict[str, str] | None = None,
        *,
        ensemble_enabled: bool = False,
    ) -> None:
        self._config: dict[str, str] = config if config is not None else dict(_DEFAULT_ROUTER_CONFIG)
        if "default" not in self._config:
            self._config["default"] = PIPELINE_SINGLE
        self._ensemble_enabled = ensemble_enabled

    @property
    def ensemble_enabled(self) -> bool:
        return self._ensemble_enabled

    def select(self, category: str | None, features: dict[str, Any] | None = None) -> str:
        """Return the pipeline name for *category*.

        When ``ensemble_enabled=False`` always returns PIPELINE_SINGLE.
        Unknown categories fall back to the "default" mapping.
        """
        if not self._ensemble_enabled:
            return PIPELINE_SINGLE

        key = (category or "").strip()
        pipeline = self._config.get(key) or self._config.get("default", PIPELINE_SINGLE)
        if pipeline not in KNOWN_PIPELINES:
            logger.warning(
                "Unknown pipeline %r for category %r; falling back to single", pipeline, key
            )
            return PIPELINE_SINGLE
        return pipeline

    def category_from_features(self, features: dict[str, Any]) -> str:
        """Derive a category label from market features (slug, category tag, etc.)."""
        # 1. Explicit category tag wins.
        explicit = str(features.get("market_category") or "").strip()
        if explicit:
            return explicit
        # 2. Slug-prefix heuristics (NBA, wc2026, elections)
        slug = str(features.get("market_slug") or "").strip().lower()
        if slug.startswith("wc2026-") or "fifa" in slug:
            return "FIFA"
        if "nba" in slug or "lal" in slug or "bos" in slug or "basketball" in slug:
            return "NBA"
        if any(k in slug for k in ("elect", "vote", "preside", "senate", "congress")):
            return "Elections"
        if any(k in slug for k in ("btc", "eth", "crypto", "sol", "polygon")):
            return "Crypto"
        return "default"

    def route(self, features: dict[str, Any]) -> str:
        """Convenience: derive category from features then select pipeline."""
        cat = self.category_from_features(features)
        return self.select(cat, features)


def build_router_from_settings(settings: Any) -> ModelRouter:
    """Build a ModelRouter from a Settings instance.

    Reads:
      settings.ensemble_enabled  (bool, default False)
      settings.ensemble_router_config  (str | None, JSON)
    """
    enabled = bool(getattr(settings, "ensemble_enabled", False))
    raw_config = getattr(settings, "ensemble_router_config", None)
    config = parse_router_config(raw_config)
    return ModelRouter(config=config, ensemble_enabled=enabled)
