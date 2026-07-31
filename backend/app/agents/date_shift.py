from __future__ import annotations

from datetime import date, timedelta

from app.config import get_settings
from app.schemas.trip import DateShiftSuggestion, WeatherDay


def rain_ratio(days: list[WeatherDay]) -> float:
    """Binary share of days classified as rainy (kept for diagnostics)."""
    if not days:
        return 0.0
    rainy = sum(1 for d in days if d.classification.value == "rainy")
    return rainy / len(days)


def wetness_score(days: list[WeatherDay]) -> float:
    """Mean daily precip probability (continuous wetness)."""
    if not days:
        return 0.0
    return sum(max(0.0, min(1.0, d.precip_probability)) for d in days) / len(days)


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
    threshold = settings.date_shift_rain_ratio
    min_improve = settings.date_shift_min_improvement

    original_wet = wetness_score(stay_weather)
    original_binary = rain_ratio(stay_weather)
    daily_pops = [d.precip_probability for d in stay_weather]
    daily_dates = [d.date for d in stay_weather]

    base_kwargs = {
        "original_rain_ratio": original_binary,
        "wetness": original_wet,
        "threshold": threshold,
        "daily_pops": daily_pops,
        "daily_dates": daily_dates,
    }

    if original_wet < threshold:
        return DateShiftSuggestion(
            **base_kwargs,
            suggested_start=start,
            suggested_end=end,
            suggested_rain_ratio=original_binary,
            suggested_wetness=original_wet,
            reason=(
                f"Requested dates look manageable (wetness {original_wet:.0%} "
                f"below threshold {threshold:.0%})."
            ),
            direction="none",
        )

    by_date = {w.date: w for w in extended}
    if not by_date:
        return DateShiftSuggestion(
            **base_kwargs,
            suggested_start=start,
            suggested_end=end,
            suggested_rain_ratio=original_binary,
            suggested_wetness=original_wet,
            reason="Not enough forecast coverage to suggest a shift.",
            direction="none",
        )

    dates_sorted = sorted(by_date.keys())
    best: tuple[float, float, str, str, str] | None = None
    for i in range(0, max(1, len(dates_sorted) - length + 1)):
        window_dates = dates_sorted[i : i + length]
        if len(window_dates) < length:
            break
        window = [by_date[d] for d in window_dates]
        w_wet = wetness_score(window)
        w_bin = rain_ratio(window)
        w_start, w_end = window_dates[0], window_dates[-1]
        if best is None or w_wet < best[0]:
            direction = "none"
            if date.fromisoformat(w_start) < start_d:
                direction = "prepone"
            elif date.fromisoformat(w_start) > start_d:
                direction = "postpone"
            best = (w_wet, w_bin, w_start, w_end, direction)

    if best is None:
        return DateShiftSuggestion(
            **base_kwargs,
            suggested_start=start,
            suggested_end=end,
            suggested_rain_ratio=original_binary,
            suggested_wetness=original_wet,
            reason="No alternate window found within the forecast horizon.",
            direction="none",
        )

    best_wet, best_bin, s, e, direction = best
    absolute_gain = original_wet - best_wet
    relative_gain = absolute_gain / original_wet if original_wet > 0 else 0.0
    good_enough = absolute_gain >= min_improve or relative_gain >= 0.25

    if not good_enough or direction == "none":
        return DateShiftSuggestion(
            **base_kwargs,
            suggested_start=start,
            suggested_end=end,
            suggested_rain_ratio=original_binary,
            suggested_wetness=original_wet,
            reason=(
                f"Stay wetness is {original_wet:.0%} but no meaningfully drier window "
                f"was found in the forecast horizon (best {best_wet:.0%})."
            ),
            direction="none",
        )

    return DateShiftSuggestion(
        **base_kwargs,
        suggested_start=s,
        suggested_end=e,
        suggested_rain_ratio=best_bin,
        suggested_wetness=best_wet,
        reason=(
            f"Stay wetness is {original_wet:.0%} (threshold {threshold:.0%}). "
            f"A {direction} to {s} through {e} drops wetness to about {best_wet:.0%}."
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
