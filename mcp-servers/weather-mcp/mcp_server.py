"""MCP tools for the weather service. Thin wrappers over service.py.

The docstring of each tool is what the agent reads, so it says what the tool
returns and what inputs are valid. (SDK note: `mcp` 2.x calls the server
class MCPServer; in 1.x it was FastMCP.)

Run directly for stdio:   python mcp_server.py
HTTP is served by app.py at /mcp.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

import service

mcp = MCPServer(
    name="weather",
    instructions=(
        "Mock weather for ten cities. Call list_supported_cities if unsure which "
        "cities exist. Temperatures are in Celsius, wind in km/h."
    ),
)


def _fail(e: service.ServiceError) -> ToolError:
    # The agent sees this as an error result it can act on (for example by
    # calling list_supported_cities), not as a broken server.
    return ToolError(f"{e.code}: {e}")


@mcp.tool()
def get_current_weather(city: str) -> dict:
    """Current weather for a supported city: temp_c, condition, humidity (%)
    and wind_kph. City names are case-insensitive, e.g. 'kochi' or 'New York'."""
    try:
        return service.get_current_weather(city)
    except service.ServiceError as e:
        raise _fail(e)


@mcp.tool()
def get_forecast(city: str, days: int = 3) -> dict:
    """Forecast for the next `days` days (1 to 7, default 3). Day 1 is tomorrow.
    Each entry has temp_c, condition and humidity."""
    try:
        return service.get_forecast(city, days)
    except service.ServiceError as e:
        raise _fail(e)


@mcp.tool()
def list_supported_cities() -> list[str]:
    """The cities this service knows about. Call this before guessing a name."""
    return service.list_supported_cities()


if __name__ == "__main__":
    mcp.run(transport="stdio")   # stdout is the protocol channel: never print() here
