"""Recorded fallback corpus for hybrid retrieval.

Integrity rule: this module never invents a place. It serves only entries
recorded in seed_corpus.json, which holds real, verifiable locations. A city
with no recorded entries returns an empty list so the caller can report that
no real places were available, rather than presenting a plausible fiction.

Refresh the corpus from live sources with scripts/build_seed_corpus.py.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas.trip import POI, RestaurantCandidate, SettingKind

CORPUS_PATH = Path(__file__).with_name("seed_corpus.json")


@lru_cache(maxsize=1)
def _corpus() -> dict[str, Any]:
    if not CORPUS_PATH.exists():
        return {"cities": {}, "neighborhood_links": {}}
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _alias_index() -> dict[str, str]:
    """Map every accepted spelling of a city to its corpus key."""
    index: dict[str, str] = {}
    for key, entry in _corpus().get("cities", {}).items():
        index[key] = key
        index[str(entry.get("display_name", key)).strip().lower()] = key
        for alias in entry.get("aliases", []):
            index[str(alias).strip().lower()] = key
    return index


def _resolve(city: str) -> dict[str, Any] | None:
    key = _alias_index().get(city.strip().lower())
    if key is None:
        return None
    return _corpus()["cities"][key]


def known_cities() -> list[str]:
    """Display names of every city with recorded entries."""
    return sorted(e.get("display_name", k) for k, e in _corpus().get("cities", {}).items())


def pois_for_city(city: str) -> list[POI]:
    entry = _resolve(city)
    if not entry:
        return []
    return [POI.model_validate({**row, "provenance": "seed"}) for row in entry.get("pois", [])]


def restaurants_for_city(city: str) -> list[RestaurantCandidate]:
    entry = _resolve(city)
    if not entry:
        return []
    return [
        RestaurantCandidate.model_validate({**row, "provenance": "seed"})
        for row in entry.get("restaurants", [])
    ]


# Neighborhood adjacency for in-memory graph expand
NEIGHBORHOOD_LINKS: dict[str, list[str]] = _corpus().get("neighborhood_links", {})

__all__ = [
    "NEIGHBORHOOD_LINKS",
    "POI",
    "RestaurantCandidate",
    "SettingKind",
    "known_cities",
    "pois_for_city",
    "restaurants_for_city",
]
