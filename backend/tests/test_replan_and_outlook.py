"""Smoke helpers for MCP service wiring and wet date-shift path.

Run:

  cd backend
  pytest tests/test_replan_and_outlook.py -q
"""

from __future__ import annotations

import os

import pytest

os.environ["MCP_STUB"] = "true"
os.environ["MCP_STUB_RAINY"] = "true"
os.environ["RESEARCH_MCP_STUB"] = "true"
os.environ["DINING_MCP_STUB"] = "true"
os.environ["DATE_SHIFT_RAIN_RATIO"] = "0.35"

from app.agents.graph import run_trip_graph
from app.config import get_settings
from app.store.trips import trip_store


@pytest.mark.asyncio
async def test_outlook_fields_always_present_when_weather_runs():
    get_settings.cache_clear()
    trip = trip_store.create("2 days in New York")
    result = await run_trip_graph(
        trip,
        city="New York",
        start_date="2026-07-21",
        end_date="2026-07-22",
        party_size=2,
        preferences=["museums"],
    )
    assert result.date_shift_suggestion is not None
    s = result.date_shift_suggestion
    assert s.daily_pops is not None
    assert s.threshold == pytest.approx(0.35)
    assert s.wetness >= 0.0


@pytest.mark.asyncio
async def test_rebuild_increments_plan_cycle_and_replays_graph():
    get_settings.cache_clear()
    trip = trip_store.create("2 days in New York")
    first = await run_trip_graph(
        trip,
        city="New York",
        start_date="2026-07-21",
        end_date="2026-07-22",
    )
    assert first.plan_cycle == 1

    # Simulate rebuild endpoint metadata + full graph re-run from planner
    replan = trip_store.create(
        f"{first.raw_prompt} Rebuild for dates 2026-07-23 to 2026-07-24.",
        replan_of=first.trip_id,
        plan_cycle=first.plan_cycle + 1,
    )
    assert replan.replan_of == first.trip_id
    assert replan.plan_cycle == 2

    result = await run_trip_graph(
        replan,
        city="New York",
        start_date="2026-07-23",
        end_date="2026-07-24",
    )
    assert result.plan_cycle == 2
    assert result.status == "completed"
    agents = {s.agent: s.status for s in result.agent_status}
    assert agents.get("planner") == "done"
    assert agents.get("researcher") in ("done", "skipped")
    assert agents.get("weather") in ("done", "skipped")
    assert agents.get("dining") in ("done", "skipped")
