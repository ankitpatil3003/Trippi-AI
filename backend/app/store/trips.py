from __future__ import annotations

import uuid
from threading import Lock

from app.schemas.trip import TripRecord


class TripStore:
    def __init__(self) -> None:
        self._trips: dict[str, TripRecord] = {}
        self._lock = Lock()

    def create(
        self,
        raw_prompt: str,
        *,
        replan_of: str | None = None,
        plan_cycle: int = 1,
    ) -> TripRecord:
        trip_id = str(uuid.uuid4())
        trip = TripRecord(
            trip_id=trip_id,
            raw_prompt=raw_prompt,
            status="queued",
            replan_of=replan_of,
            plan_cycle=plan_cycle,
        )
        with self._lock:
            self._trips[trip_id] = trip
        return trip

    def get(self, trip_id: str) -> TripRecord | None:
        with self._lock:
            trip = self._trips.get(trip_id)
            return trip.model_copy(deep=True) if trip else None

    def save(self, trip: TripRecord) -> None:
        with self._lock:
            self._trips[trip.trip_id] = trip.model_copy(deep=True)


trip_store = TripStore()
