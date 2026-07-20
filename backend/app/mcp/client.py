from __future__ import annotations

import logging
from datetime import date, timedelta

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.mcp.stub import stub_forecast
from app.schemas.trip import WeatherClass, WeatherDay

logger = logging.getLogger(__name__)


def classify_day(precip_probability: float, summary: str) -> WeatherClass:
    text = summary.lower()
    if precip_probability >= 0.55 or any(w in text for w in ("rain", "storm", "thunder", "shower")):
        return WeatherClass.RAINY
    if precip_probability >= 0.3 or "cloud" in text:
        return WeatherClass.MIXED
    return WeatherClass.CLEAR


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
async def _mcp_call_forecast(city: str, days: int) -> list[dict]:
    """Best effort MCP tool call via HTTP JSON-RPC style or langchain adapter."""
    settings = get_settings()
    import httpx

    # Prefer stub path when configured
    if settings.mcp_stub:
        raise RuntimeError("MCP_STUB enabled")

    url = settings.mcp_server_url.rstrip("/")
    # Streamable HTTP MCP tool invoke is session-based; for robustness we also
    # support a simple REST shim if present. Primary path uses stub on failure.
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Probe
        await client.get(url)
        # Attempt tools/call compatible payload used by some MCP HTTP gateways
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "get_forecast", "arguments": {"city": city, "days": days}},
        }
        resp = await client.post(url, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"MCP HTTP {resp.status_code}")
        data = resp.json()
        # Flexible parse
        result = data.get("result") or data
        if isinstance(result, dict) and "content" in result:
            # content may be text JSON
            import json

            for block in result["content"]:
                if isinstance(block, dict) and block.get("type") == "text":
                    parsed = json.loads(block["text"])
                    if isinstance(parsed, dict) and "days" in parsed:
                        return parsed["days"]
                    if isinstance(parsed, list):
                        return parsed
        if isinstance(result, dict) and "days" in result:
            return result["days"]
        if isinstance(result, list):
            return result
        raise RuntimeError("Unrecognized MCP forecast payload")


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
