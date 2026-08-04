"""Live MCP client paths: normalization, error payloads, and degraded fallback.

These paths previously had no coverage at all. Every request is mocked at
call_mcp_tool, so nothing here touches the network.
"""

import pytest
from tenacity import wait_none

from app.config import Settings
from app.mcp import dining_mcp, research

# A city deliberately absent from the recorded corpus, so the degraded path has
# nothing real to serve. Paris cannot play this role: it is recorded now.
UNSOURCED_CITY = "Reykjavik"

LIVE_POI_PAYLOAD = {
    "city": "Paris",
    "pois": [
        {
            "id": "otm_eiffel",
            "name": "Eiffel Tower",
            "city": "Paris",
            "description": "Iron lattice tower on the Champ de Mars.",
            "setting": "outdoor",
            "tags": ["towers", "view_points"],
            "lat": 48.8584,
            "lon": 2.2945,
            "score": 0.9,
            "source_urls": ["https://opentripmap.com/en/card/eiffel"],
        },
        {"id": "otm_louvre", "name": "Louvre", "city": "Paris", "setting": "indoor"},
    ],
}

LIVE_RESTAURANT_PAYLOAD = {
    "city": "Paris",
    "restaurants": [
        {
            "id": "osm_bouillon",
            "name": "Bouillon Chartier",
            "city": "Paris",
            "cuisine": "french",
            "price_tier": "local",
            "source_urls": ["https://www.openstreetmap.org/node/1"],
        }
    ],
}


@pytest.fixture(autouse=True)
def _live_mcp(monkeypatch):
    """Point both clients at a live MCP config without touching os.environ.

    Module level env mutation leaks between test modules, and the other suites
    set the stub flags to true at import time.
    """
    settings = Settings(
        mcp_stub=True,
        research_mcp_stub=False,
        dining_mcp_stub=False,
        research_mcp_url="https://research.test/mcp",
        dining_mcp_url="https://dining.test/mcp",
    )
    monkeypatch.setattr(research, "get_settings", lambda: settings)
    monkeypatch.setattr(dining_mcp, "get_settings", lambda: settings)
    # Drop tenacity backoff so failure paths do not sleep through the suite.
    research._mcp_search_pois.retry.wait = wait_none()
    dining_mcp._mcp_search_restaurants.retry.wait = wait_none()


def _stub_tool(monkeypatch, module, payload):
    async def fake_call_mcp_tool(server_name, url, tool_name, arguments):
        return payload

    monkeypatch.setattr(module, "call_mcp_tool", fake_call_mcp_tool)


@pytest.mark.asyncio
async def test_research_live_payload_is_normalized_and_marked_live(monkeypatch):
    _stub_tool(monkeypatch, research, LIVE_POI_PAYLOAD)
    pois, available = await research.fetch_pois("Paris", "museums and views")

    assert available is True
    assert [p.name for p in pois] == ["Eiffel Tower", "Louvre"]
    assert all(p.provenance == "live" for p in pois)
    assert pois[0].setting.value == "outdoor"
    assert pois[0].lat == 48.8584
    # Missing optional fields fall back to safe defaults rather than failing.
    assert pois[1].description == ""


@pytest.mark.asyncio
async def test_research_error_payload_falls_back_without_inventing(monkeypatch):
    _stub_tool(monkeypatch, research, {"error": "OpenTripMap rate limit"})
    pois, available = await research.fetch_pois(UNSOURCED_CITY, "museums")

    assert available is False
    # Not in the recorded corpus, so the honest result is nothing.
    assert pois == []


@pytest.mark.asyncio
async def test_research_error_payload_falls_back_to_recorded_corpus(monkeypatch):
    _stub_tool(monkeypatch, research, {"error": "upstream down"})
    pois, available = await research.fetch_pois("New York", "museums")

    assert available is False
    assert pois, "New York is recorded, so the fallback should serve real places"
    assert all(p.provenance == "seed" for p in pois)


@pytest.mark.asyncio
async def test_research_unnormalizable_rows_are_rejected(monkeypatch):
    _stub_tool(monkeypatch, research, {"pois": [{"id": "x"}, {"name": "   "}]})
    pois, available = await research.fetch_pois(UNSOURCED_CITY, "museums")

    assert available is False
    assert pois == []


@pytest.mark.asyncio
async def test_dining_live_payload_is_normalized_and_marked_live(monkeypatch):
    _stub_tool(monkeypatch, dining_mcp, LIVE_RESTAURANT_PAYLOAD)
    picks, available = await dining_mcp.fetch_restaurants("Paris", "bistro")

    assert available is True
    assert [r.name for r in picks] == ["Bouillon Chartier"]
    assert picks[0].provenance == "live"
    assert picks[0].price_tier == "local"


@pytest.mark.asyncio
async def test_dining_empty_result_falls_back_without_inventing(monkeypatch):
    _stub_tool(monkeypatch, dining_mcp, {"restaurants": []})
    picks, available = await dining_mcp.fetch_restaurants(UNSOURCED_CITY, "bistro")

    assert available is False
    assert picks == []


@pytest.mark.asyncio
async def test_dining_fallback_keeps_both_price_tiers(monkeypatch):
    """A city with a single fancy restaurant must still yield a fancy pick.

    Relevance ranking returns the top 8 matches, and the one fancy entry can sit
    outside that window, which left `fancy_must_try` empty for a recorded city.
    """
    _stub_tool(monkeypatch, dining_mcp, {"restaurants": []})
    picks, available = await dining_mcp.fetch_restaurants("New York", "bistro")

    assert available is False
    tiers = {p.price_tier for p in picks}
    assert "fancy" in tiers
    assert "local" in tiers
