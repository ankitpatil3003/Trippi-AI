"""Shared helpers for calling remote MCP tools over streamable HTTP."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def coerce_tool_payload(result: Any) -> Any:
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
    if hasattr(result, "content"):
        return coerce_tool_payload(result.content)
    return result


async def call_mcp_tool(server_name: str, url: str, tool_name: str, arguments: dict[str, Any]) -> Any:
    """Invoke one tool on a streamable-HTTP MCP server."""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(
        {
            server_name: {
                "url": url.rstrip("/"),
                "transport": "streamable_http",
            }
        }
    )
    tools = await client.get_tools()
    tool = next((t for t in tools if getattr(t, "name", "") == tool_name), None)
    if tool is None:
        names = [getattr(t, "name", "?") for t in tools]
        raise RuntimeError(f"{tool_name} not found on {server_name}; tools={names}")
    raw = await tool.ainvoke(arguments)
    return coerce_tool_payload(raw)
