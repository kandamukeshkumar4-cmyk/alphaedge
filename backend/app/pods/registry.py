"""Small explicit registry; pods are never discovered by import side effects."""

from __future__ import annotations

from collections.abc import Iterator

from app.pods.base import Pod


class PodRegistry:
    def __init__(self) -> None:
        self._pods: dict[str, type[Pod]] = {}

    def register(self, pod_type: type[Pod]) -> type[Pod]:
        key = getattr(pod_type, "key", "")
        if not key:
            raise ValueError("pod type must declare a non-empty key")
        if key in self._pods:
            raise ValueError(f"pod key already registered: {key}")
        self._pods[key] = pod_type
        return pod_type

    def create(self, key: str, *, config: dict | None = None) -> Pod:
        try:
            return self._pods[key](config=config)
        except KeyError as exc:
            raise KeyError(f"unknown pod key: {key}") from exc

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._pods))

    def __iter__(self) -> Iterator[tuple[str, type[Pod]]]:
        return iter(sorted(self._pods.items()))


registry = PodRegistry()
