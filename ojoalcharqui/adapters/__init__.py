"""Adapter registry, keyed by store slug."""
from __future__ import annotations

from .base import StoreAdapter
from . import smu

_REGISTRY: dict[str, StoreAdapter] = {}


def _register(adapters):
    for a in adapters:
        _REGISTRY[a.slug] = a


_register(smu.build_adapters())


def get(slug: str) -> StoreAdapter:
    if slug not in _REGISTRY:
        raise KeyError(f"unknown store '{slug}'. known: {sorted(_REGISTRY)}")
    return _REGISTRY[slug]


def all_slugs() -> list[str]:
    return sorted(_REGISTRY)


def all_adapters() -> list[StoreAdapter]:
    return [_REGISTRY[s] for s in all_slugs()]
