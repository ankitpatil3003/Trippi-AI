"""Integrity guarantees: Trippi never presents a place it cannot source.

Regression cover for the fabricated fallback, where any city outside the
recorded corpus produced invented entries such as "Paris Old Town Walk" and
"Paris Local Kitchen" and presented them as real recommendations.
"""

import os

import pytest

os.environ["MCP_STUB"] = "true"
os.environ["MCP_STUB_RAINY"] = "false"
os.environ["RESEARCH_MCP_STUB"] = "true"
os.environ["DINING_MCP_STUB"] = "true"

from app.agents.graph import run_trip_graph
from app.config import get_settings
from app.memory.seed_data import known_cities, pois_for_city, restaurants_for_city
from app.store.trips import trip_store

UNSOURCED_CITY = "Reykjavik"


def test_unknown_city_yields_nothing_rather_than_invented_places():
    assert UNSOURCED_CITY not in known_cities()
    assert pois_for_city(UNSOURCED_CITY) == []
    assert restaurants_for_city(UNSOURCED_CITY) == []


def test_no_result_is_named_after_the_requested_city():
    """The old fabrication built names by interpolating the city string."""
    for city in (UNSOURCED_CITY, "Atlantis", "Springfield"):
        names = [p.name for p in pois_for_city(city)]
        names += [r.name for r in restaurants_for_city(city)]
        assert not any(city.lower() in name.lower() for name in names)


def test_recorded_city_returns_real_places_marked_as_seed():
    pois = pois_for_city("New York")
    assert pois, "New York should be in the recorded corpus"
    assert all(p.provenance == "seed" for p in pois)
    # Attributability is the property that matters, and it holds for any city.
    # Asserting one landmark by name only tracked which sights the crawl happened
    # to rank first, and broke whenever the corpus was rebuilt.
    assert all(p.source_urls for p in pois), "every place must cite a source"
    assert all(p.name.strip() for p in pois)


def test_every_recorded_city_can_fill_a_plan():
    """Each city needs both settings and both dining tiers, or plans degrade.

    Without an indoor option a rainy day has nothing to fall back on, and without
    a fancy candidate the dining node returns an empty second pick.
    """
    for city in known_cities():
        pois = pois_for_city(city)
        restaurants = restaurants_for_city(city)
        settings = {p.setting for p in pois}
        tiers = {r.price_tier for r in restaurants}
        assert "indoor" in settings or "either" in settings, f"{city}: no indoor option"
        assert "outdoor" in settings or "either" in settings, f"{city}: no outdoor option"
        assert "fancy" in tiers, f"{city}: no fancy restaurant"
        assert "local" in tiers, f"{city}: no local restaurant"


def test_city_aliases_resolve_to_the_same_records():
    assert [p.id for p in pois_for_city("nyc")] == [p.id for p in pois_for_city("New York")]


@pytest.mark.asyncio
async def test_graph_reports_unsourced_city_instead_of_filling_it_in():
    get_settings.cache_clear()
    trip = trip_store.create(f"3 days in {UNSOURCED_CITY}")
    result = await run_trip_graph(
        trip,
        city=UNSOURCED_CITY,
        start_date="2026-07-21",
        end_date="2026-07-23",
        party_size=2,
        preferences=["views"],
    )

    assert result.pois == []
    assert result.restaurant_candidates == []

    chips = {s.agent: s for s in result.agent_status}
    assert chips["researcher"].status == "skipped"
    assert UNSOURCED_CITY in chips["researcher"].message
    assert chips["dining"].status == "skipped"

    # The trip still completes with an honest, clearly flagged buffer schedule.
    assert result.status == "completed"
    titles = [b.title for day in result.itinerary for b in day.blocks]
    assert all(UNSOURCED_CITY.lower() not in t.lower() for t in titles)
    assert all(b.fallback for day in result.itinerary for b in day.blocks)
    assert any(e.code == "weak_dining" for e in result.errors)
