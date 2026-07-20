from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.date_shift import suggest_date_shift
from app.agents.dining import rank_dining
from app.agents.packager import build_itinerary
from app.agents.validator import validate_and_patch
from app.llm.provider import parse_constraints
from app.mcp.client import fetch_forecast
from app.memory.fusion import hybrid_retrieve_pois, hybrid_retrieve_restaurants
from app.schemas.trip import AgentStatus, TripRecord
from app.store.trips import trip_store


def _merge_status(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_agent = {item["agent"]: item for item in left}
    for item in right:
        by_agent[item["agent"]] = item
    return list(by_agent.values())


class GraphState(TypedDict, total=False):
    trip_id: str
    raw_prompt: str
    city: str | None
    start_date: str | None
    end_date: str | None
    party_size: int
    preferences: list[str]
    constraints: dict[str, Any]
    pois: list[dict[str, Any]]
    restaurant_candidates: list[dict[str, Any]]
    weather_by_day: list[dict[str, Any]]
    weather_window_extended: list[dict[str, Any]]
    weather_available: bool
    date_shift_suggestion: dict[str, Any] | None
    itinerary: list[dict[str, Any]]
    dining_picks: dict[str, Any] | None
    agent_status: Annotated[list[dict[str, Any]], _merge_status]
    errors: list[dict[str, Any]]


async def _set_status(trip_id: str, agent: str, status: str, message: str = "") -> dict[str, Any]:
    item = {"agent": agent, "status": status, "message": message}
    trip = trip_store.get(trip_id)
    if trip:
        existing = [s for s in trip.agent_status if s.agent != agent]
        existing.append(AgentStatus(**item))
        trip.agent_status = existing
        if status == "running":
            trip.status = "running"
        trip_store.save(trip)
    return item


async def planner_node(state: GraphState) -> dict[str, Any]:
    trip_id = state["trip_id"]
    await _set_status(trip_id, "planner", "running", "Parsing trip intent")
    constraints = await parse_constraints(
        state["raw_prompt"],
        city=state.get("city"),
        start_date=state.get("start_date"),
        end_date=state.get("end_date"),
        party_size=state.get("party_size", 2),
        preferences=state.get("preferences") or [],
    )
    trip = trip_store.get(trip_id)
    if trip:
        trip.constraints = constraints
        trip_store.save(trip)
    status = await _set_status(trip_id, "planner", "done", f"Destination {constraints.city}")
    return {"constraints": constraints.model_dump(), "agent_status": [status]}


async def researcher_node(state: GraphState) -> dict[str, Any]:
    trip_id = state["trip_id"]
    await _set_status(trip_id, "researcher", "running", "Hybrid POI retrieval")
    c = state["constraints"]
    query = " ".join([c["city"], state.get("raw_prompt", ""), " ".join(c.get("preferences") or [])])
    pois = hybrid_retrieve_pois(c["city"], query, top_k=10, strategy="hybrid")
    restaurants = hybrid_retrieve_restaurants(c["city"], query + " restaurant local cuisine", top_k=8)
    trip = trip_store.get(trip_id)
    if trip:
        trip.pois = pois
        trip.restaurant_candidates = restaurants
        trip_store.save(trip)
    status = await _set_status(trip_id, "researcher", "done", f"{len(pois)} POIs, {len(restaurants)} restaurants")
    return {
        "pois": [p.model_dump() for p in pois],
        "restaurant_candidates": [r.model_dump() for r in restaurants],
        "agent_status": [status],
    }


async def weather_node(state: GraphState) -> dict[str, Any]:
    trip_id = state["trip_id"]
    await _set_status(trip_id, "weather", "running", "Fetching forecast via MCP")
    c = state["constraints"]
    stay, extended, available = await fetch_forecast(c["city"], c["start_date"], c["end_date"])
    suggestion = suggest_date_shift(c["start_date"], c["end_date"], stay, extended)
    trip = trip_store.get(trip_id)
    if trip:
        trip.weather_by_day = stay
        trip.weather_window_extended = extended
        trip.weather_available = available
        trip.date_shift_suggestion = suggestion
        trip_store.save(trip)
    msg = "Weather ready" if available else "Weather unavailable; using stub/degraded path"
    status = await _set_status(trip_id, "weather", "done" if available else "skipped", msg)
    return {
        "weather_by_day": [w.model_dump() for w in stay],
        "weather_window_extended": [w.model_dump() for w in extended],
        "weather_available": available,
        "date_shift_suggestion": suggestion.model_dump(),
        "agent_status": [status],
    }


async def packager_node(state: GraphState) -> dict[str, Any]:
    trip_id = state["trip_id"]
    await _set_status(trip_id, "packager", "running", "Building weather-aware schedule")
    from app.schemas.trip import POI, WeatherDay

    c = state["constraints"]
    pois = [POI.model_validate(p) for p in state.get("pois") or []]
    weather = [WeatherDay.model_validate(w) for w in state.get("weather_by_day") or []]
    itinerary = build_itinerary(c["start_date"], c["end_date"], pois, weather)
    trip = trip_store.get(trip_id)
    if trip:
        trip.itinerary = itinerary
        trip_store.save(trip)
    status = await _set_status(trip_id, "packager", "done", f"{len(itinerary)} days packed")
    return {"itinerary": [d.model_dump() for d in itinerary], "agent_status": [status]}


async def dining_node(state: GraphState) -> dict[str, Any]:
    trip_id = state["trip_id"]
    await _set_status(trip_id, "dining", "running", "Selecting must-try restaurants")
    from app.schemas.trip import ItineraryDay, RestaurantCandidate

    candidates = [RestaurantCandidate.model_validate(r) for r in state.get("restaurant_candidates") or []]
    itinerary = [ItineraryDay.model_validate(d) for d in state.get("itinerary") or []]
    picks = rank_dining(candidates, itinerary)
    trip = trip_store.get(trip_id)
    if trip:
        trip.itinerary = itinerary
        trip.dining_picks = picks
        trip_store.save(trip)
    status = await _set_status(trip_id, "dining", "done", "Local and fancy picks ready")
    return {
        "itinerary": [d.model_dump() for d in itinerary],
        "dining_picks": picks.model_dump(),
        "agent_status": [status],
    }


async def validator_node(state: GraphState) -> dict[str, Any]:
    trip_id = state["trip_id"]
    await _set_status(trip_id, "validator", "running", "Schema check")
    trip = trip_store.get(trip_id)
    if not trip:
        return {"agent_status": [{"agent": "validator", "status": "error", "message": "Trip missing"}]}
    trip = validate_and_patch(trip)
    trip.status = "completed"
    trip_store.save(trip)
    status = await _set_status(trip_id, "validator", "done", "Validated")
    return {"errors": [e.model_dump() for e in trip.errors], "agent_status": [status]}


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("planner", planner_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("weather", weather_node)
    graph.add_node("packager", packager_node)
    graph.add_node("dining", dining_node)
    graph.add_node("validator", validator_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "researcher")
    graph.add_edge("planner", "weather")
    graph.add_edge("researcher", "packager")
    graph.add_edge("weather", "packager")
    graph.add_edge("packager", "dining")
    graph.add_edge("dining", "validator")
    graph.add_edge("validator", END)
    return graph.compile()


trip_graph = build_graph()


async def run_trip_graph(trip: TripRecord, **overrides: Any) -> TripRecord:
    initial: GraphState = {
        "trip_id": trip.trip_id,
        "raw_prompt": trip.raw_prompt,
        "city": overrides.get("city"),
        "start_date": overrides.get("start_date"),
        "end_date": overrides.get("end_date"),
        "party_size": overrides.get("party_size", 2),
        "preferences": overrides.get("preferences") or [],
        "agent_status": [],
        "errors": [],
    }
    await trip_graph.ainvoke(initial)
    result = trip_store.get(trip.trip_id)
    assert result is not None
    return result
