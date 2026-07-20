from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.agents.graph import run_trip_graph
from app.schemas.trip import PlanRequest, PlanResponse, RebuildRequest, StatusResponse, TripError, TripRecord
from app.store.trips import trip_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/trips", tags=["trips"])


async def _execute_plan(trip_id: str, req: PlanRequest) -> None:
    trip = trip_store.get(trip_id)
    if not trip:
        return
    trip.status = "running"
    trip_store.save(trip)
    try:
        await run_trip_graph(
            trip,
            city=req.city,
            start_date=req.start_date,
            end_date=req.end_date,
            party_size=req.party_size,
            preferences=req.preferences,
        )
    except Exception as exc:
        logger.exception("Trip planning failed")
        failed = trip_store.get(trip_id)
        if failed:
            failed.status = "failed"
            failed.errors.append(TripError(code="plan_failed", message=str(exc), retryable=True))
            trip_store.save(failed)


@router.post("/plan", response_model=PlanResponse)
async def plan_trip(req: PlanRequest, background: BackgroundTasks) -> PlanResponse:
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")
    trip = trip_store.create(req.prompt.strip())
    background.add_task(_execute_plan, trip.trip_id, req)
    await asyncio.sleep(0)
    return PlanResponse(trip_id=trip.trip_id)


@router.get("/{trip_id}", response_model=TripRecord)
async def get_trip(trip_id: str) -> TripRecord:
    trip = trip_store.get(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.get("/{trip_id}/status", response_model=StatusResponse)
async def get_status(trip_id: str) -> StatusResponse:
    trip = trip_store.get(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return StatusResponse(
        trip_id=trip.trip_id,
        status=trip.status,
        agent_status=trip.agent_status,
        errors=trip.errors,
    )


@router.post("/{trip_id}/rebuild", response_model=PlanResponse)
async def rebuild_trip(trip_id: str, req: RebuildRequest, background: BackgroundTasks) -> PlanResponse:
    old = trip_store.get(trip_id)
    if not old:
        raise HTTPException(status_code=404, detail="Trip not found")
    city = old.constraints.city if old.constraints else None
    prefs = old.constraints.preferences if old.constraints else []
    party = old.constraints.party_size if old.constraints else 2
    prompt = (
        f"{old.raw_prompt} Rebuild for dates {req.start} to {req.end}."
        if old.raw_prompt
        else f"Trip rebuild {req.start} to {req.end}"
    )
    plan_req = PlanRequest(
        prompt=prompt,
        city=city,
        start_date=req.start,
        end_date=req.end,
        party_size=party,
        preferences=prefs,
    )
    new_trip = trip_store.create(plan_req.prompt)
    background.add_task(_execute_plan, new_trip.trip_id, plan_req)
    return PlanResponse(trip_id=new_trip.trip_id)
