"""Research MCP client: live POIs with seed fallback."""

from __future__ import annotations

import logging
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.mcp.tools import call_mcp_tool
from app.memory.fusion import hybrid_retrieve_pois
from app.schemas.trip import POI, SettingKind

logger = logging.getLogger(__name__)


def _setting(value: str | None) -> SettingKind:
    text = (value or "either").lower()
    if text == "indoor":
        return SettingKind.INDOOR
    if text == "outdoor":
        return SettingKind.OUTDOOR
    return SettingKind.EITHER


def _poi_from_row(row: dict[str, Any], city: str) -> POI | None:
    name = str(row.get("name") or "").strip()
    if not name:
        return None
    poi_id = str(row.get("id") or f"live_{name.lower().replace(' ', '_')}")
    return POI(
        id=poi_id,
        name=name,
        city=str(row.get("city") or city),
        description=str(row.get("description") or ""),
        neighborhood=str(row.get("neighborhood") or ""),
        setting=_setting(row.get("setting")),
        tags=[str(t) for t in (row.get("tags") or []) if t][:10],
        lat=float(row["lat"]) if row.get("lat") is not None else None,
        lon=float(row["lon"]) if row.get("lon") is not None else None,
        score=float(row.get("score") or 0.5),
        source_urls=[str(u) for u in (row.get("source_urls") or []) if u],
        confidence=float(row.get("confidence") or 0.7),
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20), reraise=True)
async def _mcp_search_pois(city: str, preferences: str) -> list[POI]:
    settings = get_settings()
    url = settings.research_mcp_url.strip()
    if not url:
        raise RuntimeError("RESEARCH_MCP_URL is not set")
    payload = await call_mcp_tool(
        "research",
        url,
        "search_pois",
        {"city": city, "preferences": preferences, "indoor_outdoor": "either", "limit": 12},
    )
    if isinstance(payload, dict) and payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    rows = payload.get("pois") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("Research MCP returned no POIs")
    pois: list[POI] = []
    for row in rows:
        if isinstance(row, dict):
            poi = _poi_from_row(row, city)
            if poi:
                pois.append(poi)
    if not pois:
        raise RuntimeError("Research MCP POIs could not be normalized")
    return pois


async def fetch_pois(city: str, query: str, preferences: list[str] | None = None) -> tuple[list[POI], bool]:
    """Return (pois, research_available). Seed fallback when MCP stubbed or down."""
    settings = get_settings()
    pref_text = " ".join(preferences or [])
    if settings.research_mcp_stub or not settings.research_mcp_url.strip():
        return hybrid_retrieve_pois(city, query, top_k=10, strategy="hybrid"), False

    try:
        pois = await _mcp_search_pois(city, pref_text or query)
        return pois, True
    except Exception as exc:
        logger.warning("Research MCP failed (%s); using seed fallback", exc)
        return hybrid_retrieve_pois(city, query, top_k=10, strategy="hybrid"), False
