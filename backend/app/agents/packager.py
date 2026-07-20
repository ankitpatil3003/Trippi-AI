from __future__ import annotations

from app.agents.date_shift import daterange
from app.memory.fusion import filter_by_setting
from app.schemas.trip import (
    POI,
    ItineraryBlock,
    ItineraryDay,
    SettingKind,
    WeatherClass,
    WeatherDay,
)


def _pick_pois(pool: list[POI], used: set[str], n: int) -> list[POI]:
    picked: list[POI] = []
    for poi in pool:
        if poi.id in used:
            continue
        picked.append(poi)
        used.add(poi.id)
        if len(picked) >= n:
            break
    return picked


def build_itinerary(
    start: str,
    end: str,
    pois: list[POI],
    weather_by_day: list[WeatherDay],
) -> list[ItineraryDay]:
    weather_map = {w.date: w for w in weather_by_day}
    used: set[str] = set()
    outdoor_pool = filter_by_setting(pois, SettingKind.OUTDOOR)
    indoor_pool = filter_by_setting(pois, SettingKind.INDOOR)
    either_pool = list(pois)

    days: list[ItineraryDay] = []
    for day in daterange(start, end):
        w = weather_map.get(day)
        classification = w.classification if w else WeatherClass.CLEAR
        summary = w.summary if w else ""
        blocks: list[ItineraryBlock] = []
        fallback = False

        if classification == WeatherClass.RAINY:
            morning = _pick_pois(indoor_pool, used, 1) or _pick_pois(either_pool, used, 1)
            afternoon = _pick_pois(indoor_pool, used, 1) or _pick_pois(either_pool, used, 1)
            if not morning and not afternoon:
                morning = _pick_pois(either_pool, used, 1)
                fallback = True
        elif classification == WeatherClass.CLEAR:
            morning = _pick_pois(outdoor_pool, used, 1) or _pick_pois(either_pool, used, 1)
            afternoon = _pick_pois(outdoor_pool, used, 1) or _pick_pois(either_pool, used, 1)
        else:
            morning = _pick_pois(outdoor_pool, used, 1) or _pick_pois(either_pool, used, 1)
            afternoon = _pick_pois(indoor_pool, used, 1) or _pick_pois(either_pool, used, 1)

        slots = [
            ("09:30", "12:00", morning[0] if morning else None),
            ("13:30", "16:30", afternoon[0] if afternoon else None),
        ]
        for start_t, end_t, poi in slots:
            if poi is None:
                # Guarantee non-empty day
                spare = _pick_pois(either_pool, used, 1)
                if not spare:
                    continue
                poi = spare[0]
                fallback = True
            blocks.append(
                ItineraryBlock(
                    start_time=start_t,
                    end_time=end_t,
                    title=poi.name,
                    poi_id=poi.id,
                    setting=poi.setting,
                    notes=poi.description,
                    fallback=fallback,
                    kind="poi",
                )
            )

        if not blocks:
            blocks.append(
                ItineraryBlock(
                    start_time="10:00",
                    end_time="12:00",
                    title="Neighborhood stroll or cafe hop",
                    setting=SettingKind.EITHER,
                    notes="Fallback activity when POI pool was exhausted.",
                    fallback=True,
                    kind="buffer",
                )
            )

        days.append(
            ItineraryDay(
                date=day,
                weather=classification,
                weather_summary=summary,
                blocks=blocks,
            )
        )
    return days
