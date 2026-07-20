from __future__ import annotations

from app.schemas.trip import TripError, TripRecord


def validate_and_patch(trip: TripRecord) -> TripRecord:
    errors: list[TripError] = []
    if not trip.constraints:
        errors.append(TripError(code="missing_constraints", message="Trip constraints missing.", retryable=False))
    if not trip.itinerary:
        errors.append(TripError(code="empty_itinerary", message="Itinerary is empty.", retryable=True))
        # Auto patch: one buffer day if constraints exist
        if trip.constraints:
            from app.schemas.trip import ItineraryBlock, ItineraryDay, SettingKind

            trip.itinerary = [
                ItineraryDay(
                    date=trip.constraints.start_date,
                    blocks=[
                        ItineraryBlock(
                            start_time="10:00",
                            end_time="12:00",
                            title="Explorer buffer block",
                            setting=SettingKind.EITHER,
                            fallback=True,
                            kind="buffer",
                        )
                    ],
                )
            ]
    else:
        for day in trip.itinerary:
            if not day.blocks:
                from app.schemas.trip import ItineraryBlock, SettingKind

                day.blocks.append(
                    ItineraryBlock(
                        start_time="10:00",
                        end_time="12:00",
                        title="Free exploration",
                        setting=SettingKind.EITHER,
                        fallback=True,
                        kind="buffer",
                    )
                )
                errors.append(
                    TripError(
                        code="empty_day_patched",
                        message=f"Patched empty day {day.date}.",
                        retryable=False,
                    )
                )

    if trip.dining_picks is None or (
        trip.dining_picks.local_must_try is None and trip.dining_picks.fancy_must_try is None
    ):
        errors.append(
            TripError(
                code="weak_dining",
                message="Dining picks were unavailable or weakly grounded.",
                retryable=False,
            )
        )

    trip.errors = errors
    return trip
