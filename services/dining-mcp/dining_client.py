"""Dining search via OpenTripMap + Overpass, with local/fancy ranking."""

from __future__ import annotations

import os
import re
from typing import Any

import httpx
import wikivoyage

OTM_BASE = "https://api.opentripmap.com/0.1/en/places"
OVERPASS = "https://overpass-api.de/api/interpreter"
USER_AGENT = "TrippiDiningMCP/1.0 (https://github.com/ankitpatil3003/Trippi-AI)"


def _api_key() -> str:
    return os.getenv("OPENTRIPMAP_API_KEY", "").strip()


def _error(message: str) -> dict[str, Any]:
    return {"error": message}


def sanitize_text(value: str, max_len: int = 200) -> str:
    return re.sub(r"\s+", " ", value).strip()[:max_len]


# OpenTripMap's `foods` category returns rows whose `name` is really a street
# address, for example "24 rue Chanoinesse, Paris" or "rue de la Bucherie".
# Those are not restaurants and must never reach a plan.
_STREET_WORDS = (
    "rue ", "via ", "viale ", "calle ", "avenue ", "av. ", "boulevard ", "bd ",
    "strada ", "piazza ", "plaza ", "straat ", "gracht ", "platz ", "street ",
    "road ", "lane ", "alley ",
)


def looks_like_address(name: str) -> bool:
    lowered = name.strip().lower()
    if not lowered:
        return True
    # A leading house number, "24 rue Chanoinesse".
    if re.match(r"^\d+\s*,?\s+\S", lowered):
        return True
    return lowered.startswith(_STREET_WORDS)


_FANCY_WORDS = ("fine", "gourmet", "steakhouse", "michelin", "tasting", "haute", "gastronom")
_LOCAL_WORDS = (
    "pizza", "pizzeria", "deli", "noodle", "street", "cafe", "café", "bakery",
    "taco", "bbq", "kiosk", "stand", "canteen", "trattoria", "osteria", "bistro",
    "izakaya", "ramen", "gelateria", "creperie", "crêperie", "market",
)
# Wikivoyage groups eat listings under these headings, which is a far better
# price signal than guessing from an English keyword in a French restaurant name.
_SECTION_TIERS = {
    "budget": "local",
    "cheap": "local",
    "mid-range": "mid",
    "mid range": "mid",
    "moderate": "mid",
    "splurge": "fancy",
    "expensive": "fancy",
    "upmarket": "fancy",
    "fine dining": "fancy",
}


def _tier_from_price(price: str) -> str | None:
    """Read a tier from a listing price string such as "€8-12" or "Cheap"."""
    lowered = price.lower()
    if not lowered:
        return None
    if any(w in lowered for w in ("cheap", "budget", "inexpensive")):
        return "local"
    amounts = [float(n) for n in re.findall(r"\d+(?:[.,]\d+)?", lowered.replace(",", "."))]
    # Years and phone fragments would poison the signal, so ignore large numbers.
    amounts = [a for a in amounts if 1 <= a <= 400]
    if not amounts:
        return None
    top = max(amounts)
    if top < 15:
        return "local"
    if top <= 40:
        return "mid"
    return "fancy"


def _tier_from_name(name: str, kinds: str = "", section: str = "", price: str = "") -> str:
    section_key = section.strip().lower()
    for key, tier in _SECTION_TIERS.items():
        if key in section_key:
            return tier
    text = f"{name} {kinds}".lower()
    if any(w in text for w in _FANCY_WORDS):
        return "fancy"
    by_price = _tier_from_price(price)
    if by_price:
        return by_price
    if any(w in text for w in _LOCAL_WORDS):
        return "local"
    return "mid"


async def geocode_city(city: str) -> dict[str, Any]:
    key = _api_key()
    if not key:
        return _error("OPENTRIPMAP_API_KEY is not set")
    async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": USER_AGENT}) as client:
        resp = await client.get(f"{OTM_BASE}/geoname", params={"name": city, "apikey": key})
        if resp.status_code >= 400:
            return _error(f"OpenTripMap geocode failed: HTTP {resp.status_code}")
        data = resp.json()
        if "lat" not in data or "lon" not in data:
            return _error(f"City not found: {city}")
        return {"name": data.get("name", city), "lat": data["lat"], "lon": data["lon"], "country": data.get("country")}


async def _overpass_restaurants(lat: float, lon: float, limit: int = 20) -> list[dict[str, Any]]:
    query = f"""
    [out:json][timeout:25];
    (
      node["amenity"="restaurant"](around:4000,{lat},{lon});
      node["amenity"="cafe"](around:3000,{lat},{lon});
      node["amenity"="fast_food"](around:2500,{lat},{lon});
    );
    out body {limit};
    """
    try:
        async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.post(OVERPASS, data={"data": query})
            if resp.status_code >= 400:
                return []
            elements = resp.json().get("elements") or []
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for el in elements:
        tags = el.get("tags") or {}
        name = (tags.get("name") or "").strip()
        if not name:
            continue
        cuisine = tags.get("cuisine") or tags.get("amenity") or "local"
        amenity = tags.get("amenity") or "restaurant"
        tier = "fancy" if tags.get("stars") or "fine_dining" in tags else _tier_from_name(name, cuisine)
        if amenity == "fast_food":
            tier = "local"
        out.append(
            {
                "id": f"osm_{el.get('id')}",
                "name": name,
                "city": "",
                "cuisine": cuisine.replace(";", ", "),
                "neighborhood": tags.get("addr:suburb") or tags.get("addr:neighbourhood") or "",
                "price_tier": tier,
                "description": f"{amenity} listed on OpenStreetMap",
                "tags": [amenity, cuisine],
                "score": 0.6,
                "source_urls": [f"https://www.openstreetmap.org/node/{el.get('id')}"],
                "confidence": 0.65,
            }
        )
        if len(out) >= limit:
            break
    return out


async def _wikivoyage_restaurants(city: str, limit: int) -> list[dict[str, Any]]:
    """Eat listings from Wikivoyage, which carry a price and a section heading."""
    listings = await wikivoyage.city_listings(city)
    out: list[dict[str, Any]] = []
    for row in listings:
        if row.get("kind") not in ("eat", "drink"):
            continue
        name = row["name"]
        if looks_like_address(name):
            continue
        tier = _tier_from_name(name, "", row.get("section", ""), row.get("price", ""))
        out.append(
            {
                "id": f"wv_{row['wikidata'] or re.sub(r'[^a-z0-9]+', '_', name.lower())}",
                "name": name,
                "city": city,
                "cuisine": "local",
                "neighborhood": row.get("neighborhood", ""),
                "price_tier": tier,
                "description": "",
                "tags": [t for t in (row.get("kind"), row.get("section")) if t],
                "score": 0.75 + (0.1 if row.get("price") else 0.0),
                "source_urls": [row["source_url"]],
                "confidence": 0.7,
            }
        )
    # Return everything. `_finalize` spreads across neighbourhoods and guarantees
    # tier coverage, and it can only do that from the full pool.
    return out


async def search_restaurants(city: str, cuisine_prefs: str = "", limit: int = 16) -> dict[str, Any]:
    key = _api_key()

    candidates: list[dict[str, Any]] = await _wikivoyage_restaurants(city, limit)
    sources: list[str] = ["wikivoyage"] if candidates else []

    geo = await geocode_city(city)
    if "error" in geo:
        # Wikivoyage alone is enough to answer; geocoding only feeds the extras.
        if candidates:
            return _finalize(city, candidates, cuisine_prefs, limit, sources)
        return geo

    if key:
        async with httpx.AsyncClient(timeout=25.0, headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.get(
                f"{OTM_BASE}/radius",
                params={
                    "radius": 10000,
                    "lon": geo["lon"],
                    "lat": geo["lat"],
                    "kinds": "foods",
                    "rate": 1,
                    "format": "json",
                    "limit": limit,
                    "apikey": key,
                },
            )
            if resp.status_code < 400:
                sources.append("opentripmap")
                for row in resp.json() if isinstance(resp.json(), list) else []:
                    name = (row.get("name") or "").strip()
                    if not name or looks_like_address(name):
                        continue
                    kinds = row.get("kinds") or "foods"
                    xid = row.get("xid") or name.lower().replace(" ", "_")
                    candidates.append(
                        {
                            "id": f"otm_{xid}",
                            "name": name,
                            "city": geo.get("name", city),
                            "cuisine": kinds.split(",")[0] if kinds else "local",
                            "neighborhood": "",
                            "price_tier": _tier_from_name(name, kinds),
                            "description": "Food place from OpenTripMap",
                            "tags": [k for k in kinds.split(",") if k][:6],
                            "score": float(row.get("rate") or 1) / 3.0,
                            "source_urls": [f"https://opentripmap.com/en/card/{xid}"] if row.get("xid") else [],
                            "confidence": 0.7,
                        }
                    )

    osm = await _overpass_restaurants(geo["lat"], geo["lon"], limit=limit)
    if osm:
        sources.append("openstreetmap_overpass")
    for item in osm:
        item["city"] = geo.get("name", city)
        candidates.append(item)

    return _finalize(geo.get("name", city), candidates, cuisine_prefs, limit, sources)


def _finalize(
    city: str,
    candidates: list[dict[str, Any]],
    cuisine_prefs: str,
    limit: int,
    sources: list[str],
) -> dict[str, Any]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    pref = cuisine_prefs.lower()
    for candidate in candidates:
        key_name = candidate["name"].lower()
        if key_name in seen:
            continue
        seen.add(key_name)
        if pref and pref not in key_name and pref not in (candidate.get("cuisine") or "").lower():
            candidate["score"] = float(candidate.get("score") or 0.5) * 0.9
        unique.append(candidate)

    unique.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
    chosen = wikivoyage.diversify(unique, limit)
    # Keep at least one of each tier, otherwise the ranker has no fancy candidate
    # to offer and falls back to an arbitrary pick from the wrong price band.
    picked = {id(c) for c in chosen}
    for tier in ("local", "fancy"):
        if any(c.get("price_tier") == tier for c in chosen):
            continue
        extra = next(
            (c for c in unique if c.get("price_tier") == tier and id(c) not in picked), None
        )
        if extra is not None:
            chosen.append(extra)
            picked.add(id(extra))
    return {"city": city, "restaurants": chosen, "sources": sources}


async def rank_must_try(candidates: list[dict[str, Any]] | None = None, city: str = "") -> dict[str, Any]:
    if not candidates:
        searched = await search_restaurants(city or "New York")
        if "error" in searched:
            return searched
        candidates = searched.get("restaurants") or []

    local = next((c for c in candidates if c.get("price_tier") == "local"), None)
    if local is None and candidates:
        local = candidates[0]
    fancy = next((c for c in candidates if c.get("price_tier") == "fancy"), None)
    if fancy is None:
        fancy = next((c for c in reversed(candidates) if c is not local), None)

    return {
        "local_must_try": local,
        "fancy_must_try": fancy,
        "grounding": "strong" if candidates else "weak",
    }
