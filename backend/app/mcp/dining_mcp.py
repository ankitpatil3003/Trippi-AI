"""Dining MCP client: live restaurants with seed fallback."""

from __future__ import annotations

import logging
from typing import Any, Literal

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.mcp.tools import call_mcp_tool
from app.memory.fusion import hybrid_retrieve_restaurants
from app.schemas.trip import RestaurantCandidate

logger = logging.getLogger(__name__)

PriceTier = Literal["local", "mid", "fancy"]


def _tier(value: str | None) -> PriceTier:
    text = (value or "mid").lower()
    if text == "local":
        return "local"
    if text == "fancy":
        return "fancy"
    return "mid"


def _restaurant_from_row(row: dict[str, Any], city: str) -> RestaurantCandidate | None:
    name = str(row.get("name") or "").strip()
    if not name:
        return None
    rid = str(row.get("id") or f"live_{name.lower().replace(' ', '_')}")
    return RestaurantCandidate(
        id=rid,
        name=name,
        city=str(row.get("city") or city),
        cuisine=str(row.get("cuisine") or "local"),
        neighborhood=str(row.get("neighborhood") or ""),
        price_tier=_tier(row.get("price_tier")),
        description=str(row.get("description") or ""),
        tags=[str(t) for t in (row.get("tags") or []) if t][:10],
        score=float(row.get("score") or 0.5),
        source_urls=[str(u) for u in (row.get("source_urls") or []) if u],
        confidence=float(row.get("confidence") or 0.65),
        provenance="live",
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20), reraise=True)
async def _mcp_search_restaurants(city: str, cuisine_prefs: str) -> list[RestaurantCandidate]:
    settings = get_settings()
    url = settings.dining_mcp_url.strip()
    if not url:
        raise RuntimeError("DINING_MCP_URL is not set")
    payload = await call_mcp_tool(
        "dining",
        url,
        "search_restaurants",
        {"city": city, "cuisine_prefs": cuisine_prefs, "limit": 16},
    )
    if isinstance(payload, dict) and payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    rows = payload.get("restaurants") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("Dining MCP returned no restaurants")
    out: list[RestaurantCandidate] = []
    for row in rows:
        if isinstance(row, dict):
            item = _restaurant_from_row(row, city)
            if item:
                out.append(item)
    if not out:
        raise RuntimeError("Dining MCP restaurants could not be normalized")
    return out


async def fetch_restaurants(
    city: str,
    query: str,
    preferences: list[str] | None = None,
) -> tuple[list[RestaurantCandidate], bool]:
    """Return (candidates, dining_available). Seed fallback when MCP stubbed or down."""
    settings = get_settings()
    pref_text = " ".join(preferences or [])
    if settings.dining_mcp_stub or not settings.dining_mcp_url.strip():
        return hybrid_retrieve_restaurants(city, query + " restaurant local cuisine", top_k=8), False

    try:
        restaurants = await _mcp_search_restaurants(city, pref_text or "local")
        return restaurants, True
    except Exception as exc:
        logger.warning("Dining MCP failed (%s); using seed fallback", exc)
        return hybrid_retrieve_restaurants(city, query + " restaurant local cuisine", top_k=8), False
