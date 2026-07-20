from __future__ import annotations

from datetime import date, timedelta


def stub_forecast(
    city: str,
    start: date,
    days: int,
    force_rainy: bool = False,
) -> list[dict]:
    """Deterministic forecast for local demos and CI."""
    out: list[dict] = []
    for i in range(days):
        d = start + timedelta(days=i)
        if force_rainy:
            precip = 0.8
            summary = "rain"
        else:
            # Alternate pattern so mixed trips appear in demos
            cycle = i % 3
            if cycle == 0:
                precip, summary = 0.1, "clear sky"
            elif cycle == 1:
                precip, summary = 0.35, "partly cloudy"
            else:
                precip, summary = 0.7, "light rain"
        out.append(
            {
                "date": d.isoformat(),
                "city": city,
                "precip_probability": precip,
                "summary": summary,
                "temp_c": 18 + (i % 5),
            }
        )
    return out
