from __future__ import annotations

from app.schemas.trip import DiningPick, DiningPicks, ItineraryDay, RestaurantCandidate


def rank_dining(
    candidates: list[RestaurantCandidate],
    itinerary: list[ItineraryDay],
) -> DiningPicks:
    local = next((c for c in candidates if c.price_tier == "local"), None)
    if local is None:
        local = next((c for c in candidates if c.price_tier == "mid"), None)
    fancy = next((c for c in candidates if c.price_tier == "fancy"), None)

    grounding: str = "strong" if candidates else "weak"
    days = [d.date for d in itinerary] or [None]

    local_pick = None
    fancy_pick = None
    if local:
        local_pick = DiningPick(
            restaurant_id=local.id,
            name=local.name,
            cuisine=local.cuisine,
            price_tier="local" if local.price_tier == "local" else local.price_tier,
            day_date=days[0],
            meal_slot="lunch",
            grounding=grounding if grounding == "strong" else "weak",  # type: ignore[arg-type]
            reason=f"Local must try: {local.description or local.cuisine}",
            provenance=local.provenance,
        )
    if fancy:
        fancy_day = days[-1] if days else None
        fancy_pick = DiningPick(
            restaurant_id=fancy.id,
            name=fancy.name,
            cuisine=fancy.cuisine,
            price_tier="fancy",
            day_date=fancy_day,
            meal_slot="dinner",
            grounding=grounding if grounding == "strong" else "weak",  # type: ignore[arg-type]
            reason=f"Fancy must try: {fancy.description or fancy.cuisine}",
            provenance=fancy.provenance,
        )

    # Place meal blocks onto itinerary days when possible
    if local_pick and local_pick.day_date:
        for day in itinerary:
            if day.date == local_pick.day_date:
                day.blocks.insert(
                    1,
                    _meal_block(local_pick.name, "12:00", "13:15", "local lunch", local_pick.provenance),
                )
                break
    if fancy_pick and fancy_pick.day_date:
        for day in itinerary:
            if day.date == fancy_pick.day_date:
                day.blocks.append(
                    _meal_block(fancy_pick.name, "19:00", "21:00", "fancy dinner", fancy_pick.provenance),
                )
                break

    return DiningPicks(local_must_try=local_pick, fancy_must_try=fancy_pick)


def _meal_block(title: str, start: str, end: str, notes: str, provenance: str = "seed"):
    from app.schemas.trip import ItineraryBlock, SettingKind

    return ItineraryBlock(
        start_time=start,
        end_time=end,
        title=title,
        setting=SettingKind.INDOOR,
        notes=notes,
        kind="meal",
        provenance=provenance,  # type: ignore[arg-type]
    )
