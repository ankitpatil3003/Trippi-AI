from app.mcp.client import classify_day
from app.schemas.trip import WeatherClass


def test_classify_rainy():
    assert classify_day(0.8, "light rain") == WeatherClass.RAINY


def test_classify_clear():
    assert classify_day(0.05, "clear sky") == WeatherClass.CLEAR


def test_classify_mixed():
    assert classify_day(0.35, "partly cloudy") == WeatherClass.MIXED
