from app.mcp.client import normalize_forecast_days


def test_normalize_live_mcp_forecast_shape():
    payload = {
        "city": "New York",
        "days": 2,
        "forecast": [
            {
                "date": "2026-07-22",
                "description": "light rain",
                "pop_max": 0.7,
                "temp_min_c": 18,
                "temp_max_c": 24,
            },
            {
                "date": "2026-07-23",
                "description": "clear sky",
                "pop_max": 0.1,
                "temp_min_c": 17,
                "temp_max_c": 26,
            },
        ],
    }
    days = normalize_forecast_days(payload)
    assert len(days) == 2
    assert days[0]["date"] == "2026-07-22"
    assert days[0]["precip_probability"] == 0.7
    assert "rain" in days[0]["summary"]
    assert days[1]["precip_probability"] == 0.1


def test_normalize_rejects_error_payload():
    try:
        normalize_forecast_days({"error": "Rate limit exceeded"})
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "Rate limit" in str(exc)
