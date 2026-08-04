import os

import uvicorn
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse

import research_client

load_dotenv()


def _resolve_bind() -> tuple[str, int]:
    port = int(os.getenv("PORT") or os.getenv("MCP_PORT", "8010"))
    host = os.getenv("MCP_HOST", "0.0.0.0" if os.getenv("PORT") else "127.0.0.1")
    return host, port


def _transport_security(host: str) -> TransportSecuritySettings | None:
    raw = os.getenv("MCP_ALLOWED_HOSTS", "").strip()
    if raw:
        hosts = [f"{h.strip()}:*" if ":" not in h.strip() else h.strip() for h in raw.split(",") if h.strip()]
        hosts.extend(["127.0.0.1:*", "localhost:*"])
        return TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=hosts)
    if host in ("0.0.0.0", "::") or os.getenv("PORT"):
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    return None


class _HealthASGI:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "").rstrip("/") == "/health":
            if scope.get("method") in ("GET", "HEAD"):
                await JSONResponse({"status": "ok", "service": "research-mcp"})(scope, receive, send)
                return
        await self.app(scope, receive, send)


_bind_host, _bind_port = _resolve_bind()
mcp = FastMCP(
    "research",
    host=_bind_host,
    port=_bind_port,
    transport_security=_transport_security(_bind_host),
)


@mcp.tool()
async def search_pois(city: str, preferences: str = "", indoor_outdoor: str = "either", limit: int = 12) -> dict:
    """Search notable POIs for a city via Wikivoyage listings, described from Wikipedia.

    Falls back to OpenTripMap for cities Wikivoyage does not cover. No API key is
    required for the primary path.
    """
    city = research_client.sanitize_text(city, 100)
    preferences = research_client.sanitize_text(preferences, 200)
    return await research_client.search_pois(city, preferences, indoor_outdoor, limit=limit)


@mcp.tool()
async def enrich_poi(name: str, city: str) -> dict:
    """Enrich a POI with a short Wikipedia summary when available."""
    return await research_client.enrich_poi(
        research_client.sanitize_text(name, 120),
        research_client.sanitize_text(city, 100),
    )


if __name__ == "__main__":
    mcp.settings.host = _bind_host
    mcp.settings.port = _bind_port
    asgi_app = _HealthASGI(mcp.streamable_http_app())
    uvicorn.run(asgi_app, host=_bind_host, port=_bind_port, log_level="info")
