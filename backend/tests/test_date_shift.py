from datetime import date, timedelta

from app.agents.date_shift import rain_ratio, suggest_date_shift, wetness_score
from app.mcp.client import classify_day
from app.schemas.trip import WeatherClass, WeatherDay


def test_rain_ratio():
    days = [
        WeatherDay(date="2026-07-21", classification=WeatherClass.RAINY, precip_probability=0.9),
        WeatherDay(date="2026-07-22", classification=WeatherClass.CLEAR, precip_probability=0.1),
        WeatherDay(date="2026-07-23", classification=WeatherClass.RAINY, precip_probability=0.8),
    ]
    assert abs(rain_ratio(days) - (2 / 3)) < 1e-6


def test_wetness_mean():
    days = [
        WeatherDay(date="2026-07-21", classification=WeatherClass.RAINY, precip_probability=0.5),
        WeatherDay(date="2026-07-22", classification=WeatherClass.MIXED, precip_probability=0.4),
        WeatherDay(date="2026-07-23", classification=WeatherClass.RAINY, precip_probability=0.45),
    ]
    assert abs(wetness_score(days) - 0.45) < 1e-6


def test_suggest_postpone_when_wet_live_shaped_pops():
    """OpenWeather-like pops that used to miss binary 0.6 rainy gate should still shift."""
    start = date(2026, 7, 21)
    stay = [
        WeatherDay(
            date=(start + timedelta(days=i)).isoformat(),
            classification=classify_day(0.48, "overcast clouds"),
            precip_probability=0.48,
        )
        for i in range(3)
    ]
    extended = list(stay) + [
        WeatherDay(
            date=(start + timedelta(days=i)).isoformat(),
            classification=classify_day(0.1, "clear sky"),
            precip_probability=0.1,
        )
        for i in range(3, 5)
    ]
    suggestion = suggest_date_shift(stay[0].date, stay[-1].date, stay, extended)
    assert suggestion.wetness >= 0.35
    assert suggestion.direction in ("postpone", "prepone")
    assert suggestion.suggested_wetness < suggestion.wetness - 0.1
    assert suggestion.daily_pops


def test_suggest_postpone_when_rainy():
    start = date(2026, 7, 21)
    stay = [
        WeatherDay(
            date=(start + timedelta(days=i)).isoformat(),
            classification=WeatherClass.RAINY,
            precip_probability=0.9,
        )
        for i in range(3)
    ]
    extended = list(stay) + [
        WeatherDay(
            date=(start + timedelta(days=i)).isoformat(),
            classification=WeatherClass.CLEAR,
            precip_probability=0.1,
        )
        for i in range(3, 5)
    ]
    suggestion = suggest_date_shift(stay[0].date, stay[-1].date, stay, extended)
    assert suggestion.direction in ("postpone", "prepone")
    assert suggestion.suggested_rain_ratio < suggestion.original_rain_ratio
