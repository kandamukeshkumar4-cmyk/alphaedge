"""Blend specs — the ensemble mandate as data.

Adapted from virattt/ai-hedge-fund v2 ``fund/spec.py``: a strategy is a
serializable YAML config over registered models with blend weights, and
``extra='forbid'`` everywhere so a typo fails loud at load time, not
silently at forecast time. The default spec ships as
``app/forecasting/strategies/market_blend.yaml``; a malformed or missing
file degrades to the built-in artifact+market blend rather than breaking
the forecast path.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.forecasting.alpha.base import AlphaModel
from app.forecasting.alpha.models import ArtifactModel, MarketImpliedModel

ALPHA_MODEL_REGISTRY: dict[str, type[AlphaModel]] = {
    "artifact": ArtifactModel,
    "market_implied": MarketImpliedModel,
}

DEFAULT_SPEC_PATH = Path(__file__).resolve().parent.parent / "strategies" / "market_blend.yaml"


class BlendModelSpec(BaseModel):
    """One model in a blend — a key into ALPHA_MODEL_REGISTRY plus weight."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    name: str
    weight: float = Field(default=1.0, gt=0)

    @field_validator("name")
    @classmethod
    def _known_model(cls, name: str) -> str:
        if name not in ALPHA_MODEL_REGISTRY:
            raise ValueError(
                f"unknown alpha model {name!r}; available: {sorted(ALPHA_MODEL_REGISTRY)}"
            )
        return name


class BlendSpec(BaseModel):
    """A blend strategy: models plus weights, loadable from YAML."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    name: str
    display_name: str | None = None
    models: list[BlendModelSpec] = Field(min_length=1)

    @field_validator("models")
    @classmethod
    def _unique_models(cls, models: list[BlendModelSpec]) -> list[BlendModelSpec]:
        names = [m.name for m in models]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise ValueError(f"duplicate models in blend: {sorted(duplicates)}")
        return models

    @property
    def model_weights(self) -> dict[str, float]:
        return {m.name: m.weight for m in self.models}

    def build_models(self) -> list[AlphaModel]:
        return [ALPHA_MODEL_REGISTRY[m.name]() for m in self.models]


def load_blend_spec(path: str | Path) -> BlendSpec:
    """Load a blend spec from YAML; validation errors carry pydantic detail."""
    with open(path) as f:
        data: Any = yaml.safe_load(f)
    return BlendSpec(**data)


_FALLBACK_SPEC = BlendSpec(
    name="market-blend-fallback",
    models=[
        BlendModelSpec(name="artifact", weight=0.5),
        BlendModelSpec(name="market_implied", weight=0.5),
    ],
)


@lru_cache(maxsize=1)
def default_blend_spec() -> BlendSpec:
    """The shipped spec, falling back to the built-in blend if unreadable."""
    try:
        return load_blend_spec(DEFAULT_SPEC_PATH)
    except (OSError, ValueError, TypeError):
        return _FALLBACK_SPEC
