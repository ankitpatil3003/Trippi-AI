import os

import pytest

os.environ["MCP_STUB"] = "true"
os.environ["MCP_STUB_RAINY"] = "false"

from app.agents.graph import run_trip_graph
from app.config import get_settings
from app.store.trips import trip_store


@pytest.mark.asyncio
async def test_full_graph_completes():
    get_settings.cache_clear()
    trip = trip_store.create("3 days in New York with museums and views")
    result = await run_trip_graph(
        trip,
        city="New York",
        start_date="2026-07-21",
        end_date="2026-07-23",
        party_size=2,
        preferences=["museums", "views"],
    )
    assert result.status == "completed"
    assert len(result.itinerary) == 3
    assert result.dining_picks is not None
    assert result.dining_picks.local_must_try is not None
    assert result.dining_picks.fancy_must_try is not None
    assert any(b.kind == "poi" for day in result.itinerary for b in day.blocks)
    assert result.date_shift_suggestion is not None
