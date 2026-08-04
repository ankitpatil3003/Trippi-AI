"""Wikivoyage + OpenTripMap + Wikipedia helpers for Research MCP."""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote

import httpx
import wikivoyage

OTM_BASE = "https://api.opentripmap.com/0.1/en/places"
WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
WIKIVOYAGE_SUMMARY = "https://en.wikivoyage.org/api/rest_v1/page/summary/{title}"
USER_AGENT = "TrippiResearchMCP/1.0 (https://github.com/ankitpatil3003/Trippi-AI)"


def _api_key() -> str:
    return os.getenv("OPENTRIPMAP_API_KEY", "").strip()


def _error(message: str) -> dict[str, Any]:
    return {"error": message}


def _setting_from_kinds(kinds: str) -> str:
    text = kinds.lower()
    indoor_keys = ("museums", "theatres", "cinema", "aquariums", "indoor", "galleries")
    outdoor_keys = ("parks", "view_points", "towers", "bridges", "beaches", "natural", "gardens")
    indoor = any(k in text for k in indoor_keys)
    outdoor = any(k in text for k in outdoor_keys)
    if indoor and not outdoor:
        return "indoor"
    if outdoor and not indoor:
        return "outdoor"
    return "either"


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
        return {
            "name": data.get("name", city),
            "country": data.get("country"),
            "lat": data["lat"],
            "lon": data["lon"],
        }


# Names are frequently in the local language, so English keywords alone leave most
# European and Japanese sights unclassified.
_INDOOR_WORDS = (
    "museum", "musee", "musée", "museo", "museu", "muzeum", "gallery", "galerie",
    "galleria", "cathedral", "cathedrale", "cathédrale", "catedral", "duomo",
    "basilica", "basilique", "church", "chiesa", "iglesia", "eglise", "église",
    "kirche", "chapel", "chapelle", "cappella", "palace", "palais", "palazzo",
    "palacio", "theatre", "theater", "teatro", "théâtre", "opera", "aquarium",
    "library", "biblioteca", "castle", "castello", "chateau", "château",
    "temple", "shrine", "jinja", "synagogue", "mosque", "exhibition", "cinema",
    "hall", "kunsthal", "rijksmuseum",
)
_OUTDOOR_WORDS = (
    "park", "parc", "parco", "parque", "garden", "jardin", "giardino", "jardim",
    "tuin", "gyoen", "koen", "square", "plaza", "piazza", "place ", "platz",
    "bridge", "pont", "ponte", "puente", "brug", "tower", "tour ", "torre",
    "beach", "playa", "market", "mercado", "mercato", "marche", "marché",
    "cemetery", "promenade", "canal", "gracht", "hill", "island", "zoo",
    "fountain", "fontaine", "fontana", "viewpoint", "monument", "arch", "arc de",
    "pier", "quay", "forum", "colosseum", "colosseo", "stadium", "waterfront",
)


def _word_pattern(words: tuple[str, ...]) -> re.Pattern[str]:
    """Match whole words only.

    Substring matching mis-tags constantly: "research" contains "arch", so the
    Schomburg Center reads as outdoor, and a rainy day would send you to a
    library's front steps.
    """
    return re.compile(r"\b(?:" + "|".join(re.escape(w.strip()) for w in words) + r")\b")


_INDOOR_RE = _word_pattern(_INDOOR_WORDS)
_OUTDOOR_RE = _word_pattern(_OUTDOOR_WORDS)


def _classify(text: str) -> str:
    lowered = text.lower()
    indoor = bool(_INDOOR_RE.search(lowered))
    outdoor = bool(_OUTDOOR_RE.search(lowered))
    if indoor and not outdoor:
        return "indoor"
    if outdoor and not indoor:
        return "outdoor"
    return "either"


def _setting_from_text(name: str, description: str = "") -> str:
    """Classify indoor vs outdoor, letting the name win.

    Descriptions mention neighbouring features constantly, so "Jardin des
    Tuileries" reads as both a garden and a palace and collapses to `either`.
    The name is the more reliable signal, so only consult the description when
    the name says nothing.
    """
    by_name = _classify(name)
    if by_name != "either":
        return by_name
    return _classify(description)


async def search_pois(
    city: str,
    preferences: str = "",
    indoor_outdoor: str = "either",
    limit: int = 12,
) -> dict[str, Any]:
    """Find notable sights for a city.

    Wikivoyage is the primary source because it knows what a city is known for.
    OpenTripMap `/radius` is a proximity index: it returns the nearest places to a
    point and caps at 500 rows, so in a large city it never reaches the landmarks.
    It stays as a fallback for places Wikivoyage does not cover.
    """
    listings = await wikivoyage.city_listings(city)
    sights = [r for r in listings if r["kind"] in ("see", "do")]
    if sights:
        return await _pois_from_listings(city, sights, preferences, indoor_outdoor, limit)
    return await _search_pois_otm(city, preferences, indoor_outdoor, limit)


async def _pois_from_listings(
    city: str,
    sights: list[dict[str, Any]],
    preferences: str,
    indoor_outdoor: str,
    limit: int,
) -> dict[str, Any]:
    # Describe a wider slice than requested. Indoor/outdoor filtering discards
    # some, and the neighbourhood spread below needs enough districts to draw
    # from, so a narrow pool would put every result on one street.
    pool = sights[: max(limit * 6, 60)]
    described = await wikivoyage.describe(pool)

    pref = preferences.lower()
    pref_words = [w for w in re.split(r"[^a-z]+", pref) if len(w) > 3]

    pois: list[dict[str, Any]] = []
    for row in pool:
        name = row["name"]
        info = described.get(name, {})
        description = info.get("description", "")
        setting = _setting_from_text(name, description)
        if indoor_outdoor in ("indoor", "outdoor") and setting not in (indoor_outdoor, "either"):
            continue
        source_urls = [u for u in (info.get("url"), row.get("source_url")) if u]
        score = wikivoyage.notability(row)
        if pref_words:
            haystack = f"{name} {description}".lower()
            score += sum(1.0 for w in pref_words if w in haystack)
        pois.append(
            {
                "id": f"wv_{row['wikidata'] or re.sub(r'[^a-z0-9]+', '_', name.lower())}",
                "name": name,
                "city": city,
                "description": description,
                "neighborhood": row.get("neighborhood", ""),
                "setting": setting,
                "tags": [t for t in (row.get("kind"), row.get("section")) if t],
                "lat": row.get("lat"),
                "lon": row.get("lon"),
                "score": score,
                "source_urls": source_urls,
                "confidence": 0.85 if row.get("wikidata") else 0.6,
            }
        )

    pois.sort(key=lambda p: p["score"], reverse=True)
    pois = wikivoyage.diversify(pois, limit)
    # Normalise to 0..1 so downstream fusion sees a comparable scale.
    top = max((p["score"] for p in pois), default=1.0) or 1.0
    for poi in pois:
        poi["score"] = round(min(1.0, max(0.0, poi["score"] / top)), 4)

    context = ""
    sources = ["wikivoyage"]
    if any(p["description"] for p in pois):
        sources.append("wikipedia")
    voyage = await wikivoyage_summary(city)
    if "error" not in voyage and voyage.get("extract"):
        context = str(voyage["extract"])

    lats = [p["lat"] for p in pois if p["lat"] is not None]
    lons = [p["lon"] for p in pois if p["lon"] is not None]
    coordinates = (
        {"lat": sum(lats) / len(lats), "lon": sum(lons) / len(lons)} if lats and lons else {}
    )
    return {
        "city": city,
        "coordinates": coordinates,
        "pois": pois,
        "city_context": context,
        "sources": sources,
    }


async def _search_pois_otm(
    city: str,
    preferences: str = "",
    indoor_outdoor: str = "either",
    limit: int = 12,
) -> dict[str, Any]:
    key = _api_key()
    if not key:
        return _error("OPENTRIPMAP_API_KEY is not set")

    geo = await geocode_city(city)
    if "error" in geo:
        return geo

    kinds = "interesting_places"
    pref = preferences.lower()
    if "museum" in pref or "art" in pref:
        kinds = "museums,cultural"
    elif "park" in pref or "view" in pref or "outdoor" in pref:
        kinds = "natural,view_points,gardens_and_parks,bridges"
    elif "food" in pref or "market" in pref:
        kinds = "foods,shops"

    radius = 12000
    async with httpx.AsyncClient(timeout=25.0, headers={"User-Agent": USER_AGENT}) as client:
        resp = await client.get(
            f"{OTM_BASE}/radius",
            params={
                "radius": radius,
                "lon": geo["lon"],
                "lat": geo["lat"],
                "kinds": kinds,
                "rate": 2,
                "format": "json",
                "limit": max(limit * 2, 20),
                "apikey": key,
            },
        )
        if resp.status_code >= 400:
            return _error(f"OpenTripMap search failed: HTTP {resp.status_code}")
        rows = resp.json() if isinstance(resp.json(), list) else []

    pois: list[dict[str, Any]] = []
    for row in rows:
        name = (row.get("name") or "").strip()
        if not name:
            continue
        kinds_str = row.get("kinds") or ""
        setting = _setting_from_kinds(kinds_str)
        if indoor_outdoor in ("indoor", "outdoor") and setting not in (indoor_outdoor, "either"):
            continue
        xid = row.get("xid") or name.lower().replace(" ", "_")
        pois.append(
            {
                "id": f"otm_{xid}",
                "name": name,
                "city": geo.get("name", city),
                "description": "",
                "neighborhood": "",
                "setting": setting,
                "tags": [k for k in kinds_str.split(",") if k][:8],
                "lat": (row.get("point") or {}).get("lat"),
                "lon": (row.get("point") or {}).get("lon"),
                "score": float(row.get("rate") or 1) / 3.0,
                "source_urls": [f"https://opentripmap.com/en/card/{xid}"] if row.get("xid") else [],
                "confidence": 0.7,
            }
        )
        if len(pois) >= limit:
            break

    city_name = geo.get("name", city)
    voyage = await wikivoyage_summary(city_name)
    wiki = await wikipedia_summary(city_name)
    context = ""
    sources = ["opentripmap"]
    if "error" not in voyage and voyage.get("extract"):
        context = str(voyage["extract"])
        sources.append("wikivoyage")
    elif "error" not in wiki and wiki.get("extract"):
        context = str(wiki["extract"])
        sources.append("wikipedia")
    return {
        "city": city_name,
        "coordinates": {"lat": geo["lat"], "lon": geo["lon"]},
        "pois": pois,
        "city_context": context,
        "sources": sources,
    }


async def _wiki_family_summary(template: str, title: str, label: str) -> dict[str, Any]:
    url = template.format(title=quote(title.replace(" ", "_")))
    async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": USER_AGENT}) as client:
        resp = await client.get(url)
        if resp.status_code == 404:
            return _error(f"{label} page not found for {title}")
        if resp.status_code >= 400:
            return _error(f"{label} failed: HTTP {resp.status_code}")
        data = resp.json()
        return {
            "title": data.get("title", title),
            "extract": data.get("extract", ""),
            "url": (data.get("content_urls") or {}).get("desktop", {}).get("page", ""),
        }


async def wikipedia_summary(title: str) -> dict[str, Any]:
    return await _wiki_family_summary(WIKI_SUMMARY, title, "Wikipedia")


async def wikivoyage_summary(title: str) -> dict[str, Any]:
    return await _wiki_family_summary(WIKIVOYAGE_SUMMARY, title, "Wikivoyage")


async def enrich_poi(name: str, city: str) -> dict[str, Any]:
    """Light enrichment via Wikipedia summary (allowlisted public API)."""
    # Prefer "Name, City" then Name
    for title in (f"{name}, {city}", name):
        summary = await wikipedia_summary(title)
        if "error" not in summary and summary.get("extract"):
            return {
                "name": name,
                "city": city,
                "description": summary["extract"][:600],
                "source_urls": [u for u in [summary.get("url")] if u],
                "confidence": 0.75,
            }
    return {
        "name": name,
        "city": city,
        "description": "",
        "source_urls": [],
        "confidence": 0.3,
        "note": "No Wikipedia enrichment found",
    }


def sanitize_text(value: str, max_len: int = 200) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned[:max_len]
