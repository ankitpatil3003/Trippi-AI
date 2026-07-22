"""Dining search via OpenTripMap + Overpass, with local/fancy ranking."""

from __future__ import annotations

import os
import re
from typing import Any

import httpx

OTM_BASE = "https://api.opentripmap.com/0.1/en/places"
OVERPASS = "https://overpass-api.de/api/interpreter"
USER_AGENT = "TrippiDiningMCP/1.0 (https://github.com/ankitpatil3003/Trippi-AI)"


def _api_key() -> str:
    return os.getenv("OPENTRIPMAP_API_KEY", "").strip()


def _error(message: str) -> dict[str, Any]:
    return {"error": message}


def sanitize_text(value: str, max_len: int = 200) -> str:
    return re.sub(r"\s+", " ", value).strip()[:max_len]


def _tier_from_name(name: str, kinds: str) -> str:
    text = f"{name} {kinds}".lower()
    if any(w in text for w in ("fine", "gourmet", "steakhouse", "michelin", "tasting")):
        return "fancy"
    if any(w in text for w in ("pizza", "deli", "noodle", "street", "cafe", "bakery", "taco", "bbq")):
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


async def search_restaurants(city: str, cuisine_prefs: str = "", limit: int = 16) -> dict[str, Any]:
    key = _api_key()
    geo = await geocode_city(city)
    if "error" in geo:
        return geo

    candidates: list[dict[str, Any]] = []
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
                for row in resp.json() if isinstance(resp.json(), list) else []:
                    name = (row.get("name") or "").strip()
                    if not name:
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
    for item in osm:
        item["city"] = geo.get("name", city)
        candidates.append(item)

    # Deduplicate by lowercase name
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    pref = cuisine_prefs.lower()
    for c in candidates:
        key_name = c["name"].lower()
        if key_name in seen:
            continue
        seen.add(key_name)
        if pref and pref not in key_name and pref not in (c.get("cuisine") or "").lower():
            c["score"] = float(c.get("score") or 0.5) * 0.9
        unique.append(c)

    unique.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
    return {
        "city": geo.get("name", city),
        "restaurants": unique[:limit],
        "sources": ["opentripmap", "openstreetmap_overpass"],
    }


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
