"""Record a real-data snapshot into backend/app/memory/seed_corpus.json.

The corpus is Trippi's degraded-mode fallback. It must contain only real,
verifiable places, so it is built by calling the same live sources the MCP
services use (Wikivoyage, Wikipedia, OpenTripMap, OpenStreetMap) and recording
the result. Nothing here invents data: a city that fails to fetch is skipped,
not filled in.

An OpenTripMap key is optional. Wikivoyage and Wikipedia carry the build on
their own, and the key only widens the restaurant candidate pool.

Usage:
    python scripts/build_seed_corpus.py
    export OPENTRIPMAP_API_KEY=...        # optional, or services/research-mcp/.env
    python scripts/build_seed_corpus.py --cities "Paris,Tokyo"   # refresh a subset
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "backend" / "app" / "memory" / "seed_corpus.json"

DEFAULT_CITIES = [
    "New York",
    "Paris",
    "London",
    "Tokyo",
    "Rome",
    "Barcelona",
    "Amsterdam",
    "Singapore",
    "Dubai",
    "San Francisco",
]

ALIASES: dict[str, list[str]] = {
    "New York": ["nyc", "ny", "manhattan", "new york city"],
    "San Francisco": ["sf", "san fran"],
    "Rome": ["roma"],
    "Tokyo": ["tokio"],
}

# Two passes so the packager has both an indoor and an outdoor pool to draw on.
# The preference text biases ranking; research_client classifies each result's
# setting from its name, so the two passes overlap and are merged by id.
POI_PASSES = [("museums art culture", "indoor"), ("parks views outdoor gardens", "outdoor")]


def _load_module(name: str, path: Path):
    # The service modules import their local `wikivoyage` helper, so the service
    # directory has to be importable before the module body runs.
    directory = str(path.parent)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_key() -> str:
    key = os.getenv("OPENTRIPMAP_API_KEY", "").strip()
    if key:
        return key
    # Fall back to a service .env so the script works right after local setup.
    for candidate in (
        ROOT / "services" / "research-mcp" / ".env",
        ROOT / "services" / "dining-mcp" / ".env",
    ):
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("OPENTRIPMAP_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


async def _collect_pois(research: Any, city: str, per_pass: int) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for preferences, want in POI_PASSES:
        result = await research.search_pois(city, preferences=preferences, limit=per_pass)
        if "error" in result:
            raise RuntimeError(f"search_pois({city}, {want}): {result['error']}")
        for row in result.get("pois", []):
            by_id.setdefault(row["id"], row)

    # OpenTripMap returns empty descriptions. Enrich from Wikipedia so itinerary
    # blocks carry real, attributable notes instead of blank text.
    for row in by_id.values():
        if row.get("description"):
            continue
        enriched = await research.enrich_poi(row["name"], city)
        if enriched.get("description"):
            row["description"] = research.sanitize_text(enriched["description"], max_len=280)
            row["source_urls"] = list({*row.get("source_urls", []), *enriched.get("source_urls", [])})
    return list(by_id.values())


async def build_city(research: Any, dining: Any, city: str, limit: int) -> dict[str, Any]:
    pois = await _collect_pois(research, city, per_pass=limit)
    restaurants_result = await dining.search_restaurants(city, limit=limit)
    if "error" in restaurants_result:
        raise RuntimeError(f"search_restaurants({city}): {restaurants_result['error']}")
    restaurants = restaurants_result.get("restaurants", [])
    if not pois or not restaurants:
        raise RuntimeError(f"{city}: empty result (pois={len(pois)}, restaurants={len(restaurants)})")
    return {
        "display_name": city,
        "aliases": ALIASES.get(city, []),
        "pois": pois,
        "restaurants": restaurants,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cities", default="", help="Comma separated subset to refresh")
    parser.add_argument("--limit", type=int, default=12, help="Items requested per source")
    args = parser.parse_args()

    # Wikivoyage and Wikipedia need no credentials, so the build works without a
    # key. OpenTripMap and Overpass only add extra candidates when one is present.
    key = _load_key()
    if key:
        os.environ["OPENTRIPMAP_API_KEY"] = key
    else:
        print("No OPENTRIPMAP_API_KEY found. Building from Wikivoyage and Wikipedia only.")

    research = _load_module("_research_client", ROOT / "services" / "research-mcp" / "research_client.py")
    dining = _load_module("_dining_client", ROOT / "services" / "dining-mcp" / "dining_client.py")

    corpus: dict[str, Any] = (
        json.loads(CORPUS.read_text(encoding="utf-8"))
        if CORPUS.exists()
        else {"cities": {}, "neighborhood_links": {}}
    )
    corpus.setdefault("cities", {})
    corpus.setdefault("neighborhood_links", {})
    corpus["note"] = (
        "Recorded fallback corpus. Every entry is a real place fetched from "
        "Wikivoyage, Wikipedia, OpenTripMap, and OpenStreetMap. "
        "Rebuild with scripts/build_seed_corpus.py."
    )

    cities = [c.strip() for c in args.cities.split(",") if c.strip()] or DEFAULT_CITIES
    failed: list[str] = []
    for city in cities:
        try:
            entry = await build_city(research, dining, city, args.limit)
        except Exception as exc:
            # Skip rather than write a partial or invented entry.
            print(f"  SKIP {city}: {exc}")
            failed.append(city)
            continue
        corpus["cities"][city.lower()] = entry
        print(f"  OK   {city}: {len(entry['pois'])} POIs, {len(entry['restaurants'])} restaurants")

    CORPUS.write_text(json.dumps(corpus, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote {CORPUS} with {len(corpus['cities'])} cities")
    if failed:
        print(f"Skipped (left unchanged): {', '.join(failed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
