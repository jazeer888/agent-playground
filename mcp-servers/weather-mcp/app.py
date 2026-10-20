"""Weather service: REST at /api/..., MCP at /mcp, one process.

    curl / app   ──► FastAPI routes (/api)     ──┐
                                                 ├──► service.py
    AI agent     ──► MCP app mounted at /mcp  ──┘

Run:  python app.py        (listens on http://127.0.0.1:8002)
See bookstore-mcp/app.py for the same structure with more comments.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import service
from mcp_server import mcp

PORT = 8002

mcp_app = mcp.streamable_http_app()   # the MCP protocol handler, served at /mcp


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the MCP session manager for the life of the process (a mounted
    # app's own lifespan is not run by Starlette, so we do it here).
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="Weather", lifespan=lifespan)


@app.exception_handler(service.ServiceError)
async def service_error(_: Request, e: service.ServiceError):
    return JSONResponse(status_code=e.status, content={"error": e.code, "message": str(e)})


# --- REST --------------------------------------------------------------------------------


@app.get("/api/health")
def api_health():
    return {"status": "ok", "service": "weather", "mcp": "/mcp"}


@app.get("/api/cities")
def api_cities():
    return service.list_supported_cities()


@app.get("/api/weather/{city}")
def api_weather(city: str, days: int | None = None):
    # One route, two shapes: /api/weather/kochi -> current; ?days=3 -> forecast.
    if days is None:
        return service.get_current_weather(city)
    return service.get_forecast(city, days)


# --- MCP ---------------------------------------------------------------------------------
# Mounted last so the /api routes above are matched first.
app.mount("/", mcp_app)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT)
