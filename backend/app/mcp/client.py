from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.mcp.stub import stub_forecast
from app.schemas.trip import WeatherClass, WeatherDay

logger = logging.getLogger(__name__)


def classify_day(precip_probability: float, summary: str) -> WeatherClass:
    text = summary.lower()
    if precip_probability >= 0.40 or any(w in text for w in ("rain", "storm", "thunder", "shower")):
        return WeatherClass.RAINY
    if precip_probability >= 0.20 or "cloud" in text:
        return WeatherClass.MIXED
    return WeatherClass.CLEAR


def _coerce_tool_payload(result: Any) -> Any:
    """Normalize LangChain / MCP tool return shapes to plain Python."""
    if result is None:
        return None
    if isinstance(result, (dict, list)):
        return result
    if isinstance(result, str):
        text = result.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return result
        return result
    # Some adapters wrap content blocks
    if hasattr(result, "content"):
        return _coerce_tool_payload(result.content)
    return result


def normalize_forecast_days(payload: Any) -> list[dict[str, Any]]:
    """
    Map MCP get_forecast output into Trippi day dicts.

    Live weather MCP returns:
      { city, forecast: [{ date, description, pop_max, temp_min_c, temp_max_c, ... }], days: N }
    """
    data = _coerce_tool_payload(payload)
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(str(data["error"]))

    rows: list[Any] = []
    if isinstance(data, dict):
        if isinstance(data.get("forecast"), list):
            rows = data["forecast"]
        elif isinstance(data.get("days"), list):
            rows = data["days"]
    elif isinstance(data, list):
        rows = data

    out: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        precip = item.get("precip_probability", item.get("pop_max", item.get("pop", 0.2)))
        try:
            precip_f = float(precip if precip is not None else 0.2)
        except (TypeError, ValueError):
            precip_f = 0.2
        temp = item.get("temp_c")
        if temp is None:
            tmax = item.get("temp_max_c")
            tmin = item.get("temp_min_c")
            if tmax is not None and tmin is not None:
                try:
                    temp = (float(tmax) + float(tmin)) / 2.0
                except (TypeError, ValueError):
                    temp = None
            elif tmax is not None:
                temp = tmax
        out.append(
            {
                "date": item.get("date"),
                "summary": str(item.get("summary") or item.get("description") or "clear"),
                "precip_probability": precip_f,
                "temp_c": temp,
            }
        )
    if not out:
        raise RuntimeError("MCP forecast returned no daily rows")
    return out


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20), reraise=True)
async def _mcp_call_forecast(city: str, days: int) -> list[dict]:
    """Call live Weather MCP via streamable HTTP (same path as MCP-Weather agent)."""
    settings = get_settings()
    if settings.mcp_stub:
        raise RuntimeError("MCP_STUB enabled")

    from langchain_mcp_adapters.client import MultiServerMCPClient

    url = settings.resolved_weather_mcp_url()
    client = MultiServerMCPClient(
        {
            "weather": {
                "url": url,
                "transport": "streamable_http",
            }
        }
    )
    tools = await client.get_tools()
    forecast_tool = next((t for t in tools if getattr(t, "name", "") == "get_forecast"), None)
    if forecast_tool is None:
        names = [getattr(t, "name", "?") for t in tools]
        raise RuntimeError(f"get_forecast tool not found on MCP server; tools={names}")

    raw = await forecast_tool.ainvoke({"city": city, "days": max(1, min(5, days))})
    return normalize_forecast_days(raw)


async def fetch_forecast(city: str, start: str, end: str) -> tuple[list[WeatherDay], list[WeatherDay], bool]:
    """Return (stay_days, extended_window, available)."""
    settings = get_settings()
    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    stay_len = max(1, (end_d - start_d).days + 1)
    extended_len = min(5, stay_len + 2)

    raw_days: list[dict] | None = None
    available = True
    try:
        if settings.mcp_stub:
            raw_days = stub_forecast(city, start_d, extended_len, force_rainy=settings.mcp_stub_rainy)
        else:
            raw_days = await _mcp_call_forecast(city, extended_len)
    except Exception as exc:
        logger.warning("MCP forecast failed (%s); using stub fallback", exc)
        available = False
        raw_days = stub_forecast(city, start_d, extended_len, force_rainy=settings.mcp_stub_rainy)

    weather: list[WeatherDay] = []
    for i, item in enumerate(raw_days or []):
        day_date = item.get("date") or (start_d + timedelta(days=i)).isoformat()
        precip = float(item.get("precip_probability", item.get("pop", 0.2)))
        summary = str(item.get("summary", item.get("description", "clear")))
        temp = item.get("temp_c", item.get("temp"))
        weather.append(
            WeatherDay(
                date=day_date,
                classification=classify_day(precip, summary),
                summary=summary,
                precip_probability=precip,
                temp_c=float(temp) if temp is not None else None,
            )
        )

    stay_dates = {(start_d + timedelta(days=i)).isoformat() for i in range(stay_len)}
    stay = [w for w in weather if w.date in stay_dates]
    if not stay:
        stay = weather[:stay_len]
    return stay, weather, available
