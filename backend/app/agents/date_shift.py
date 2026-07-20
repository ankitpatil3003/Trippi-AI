from __future__ import annotations

from datetime import date, timedelta

from app.config import get_settings
from app.schemas.trip import DateShiftSuggestion, WeatherDay


def rain_ratio(days: list[WeatherDay]) -> float:
    if not days:
        return 0.0
    rainy = sum(1 for d in days if d.classification.value == "rainy")
    return rainy / len(days)


def suggest_date_shift(
    start: str,
    end: str,
    stay_weather: list[WeatherDay],
    extended: list[WeatherDay],
) -> DateShiftSuggestion:
    settings = get_settings()
    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    length = (end_d - start_d).days + 1
    original = rain_ratio(stay_weather)

    if original < settings.date_shift_rain_ratio:
        return DateShiftSuggestion(
            original_rain_ratio=original,
            suggested_start=start,
            suggested_end=end,
            suggested_rain_ratio=original,
            reason="Requested dates already look enjoyable enough.",
            direction="none",
        )

    # Score every same-length window inside the extended forecast
    by_date = {w.date: w for w in extended}
    if not by_date:
        return DateShiftSuggestion(
            original_rain_ratio=original,
            suggested_start=start,
            suggested_end=end,
            suggested_rain_ratio=original,
            reason="Not enough forecast coverage to suggest a shift.",
            direction="none",
        )

    dates_sorted = sorted(by_date.keys())
    best: tuple[float, str, str, str] | None = None
    for i in range(0, max(1, len(dates_sorted) - length + 1)):
        window_dates = dates_sorted[i : i + length]
        if len(window_dates) < length:
            break
        window = [by_date[d] for d in window_dates]
        ratio = rain_ratio(window)
        w_start, w_end = window_dates[0], window_dates[-1]
        if best is None or ratio < best[0]:
            direction = "none"
            if date.fromisoformat(w_start) < start_d:
                direction = "prepone"
            elif date.fromisoformat(w_start) > start_d:
                direction = "postpone"
            best = (ratio, w_start, w_end, direction)

    if best is None or best[0] >= original - 0.05:
        return DateShiftSuggestion(
            original_rain_ratio=original,
            suggested_start=start,
            suggested_end=end,
            suggested_rain_ratio=original,
            reason="No meaningfully drier window found within the forecast horizon.",
            direction="none",
        )

    ratio, s, e, direction = best
    return DateShiftSuggestion(
        original_rain_ratio=original,
        suggested_start=s,
        suggested_end=e,
        suggested_rain_ratio=ratio,
        reason=(
            f"About {original:.0%} of your requested days look rainy. "
            f"A {direction} to {s} through {e} drops rain ratio to about {ratio:.0%}."
        ),
        direction=direction if direction in ("postpone", "prepone") else "postpone",
    )


def daterange(start: str, end: str) -> list[str]:
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    out: list[str] = []
    cur = s
    while cur <= e:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out
