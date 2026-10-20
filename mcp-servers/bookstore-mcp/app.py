"""One process, two doors: REST at /api/... and MCP at /mcp.

    browser / curl ──► FastAPI routes (/api, /)  ──┐
                                                   ├──► service.py (the only logic)
    AI agent       ──► MCP app mounted at /mcp  ──┘

Run:  python app.py        (listens on http://127.0.0.1:8001)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

import service
from mcp_server import mcp

PORT = 8001
STATIC = Path(__file__).parent / "static"

# The MCP HTTP app. One instance, created once. It handles the JSON-RPC
# protocol and sessions; our tools in mcp_server.py do the actual work.
mcp_app = mcp.streamable_http_app()   # serves at /mcp inside this sub-app


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The MCP session manager needs a running task group for the whole life
    # of the process. Starlette does not start a mounted app's lifespan, so we
    # start it here, inside FastAPI's own lifespan. Forgetting this is the
    # classic mistake: /mcp then fails with "Task group is not initialized".
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="Bookstore", lifespan=lifespan)


# One handler turns every ServiceError into a clean JSON error with the right
# status. Routes below stay free of try/except.
@app.exception_handler(service.ServiceError)
async def service_error(_: Request, e: service.ServiceError):
    return JSONResponse(status_code=e.status, content={"error": e.code, "message": str(e)})


# --- REST ---------------------------------------------------------------------------------


@app.get("/api/books")
def api_list_books():
    return service.list_books()


@app.get("/api/books/search")           # declared BEFORE /api/books/{book_id}, or "search"
def api_search_books(q: str = ""):      # would be taken as a book id
    return service.search_books(q)


@app.get("/api/books/{book_id}")
def api_get_book(book_id: str):
    return service.get_book(book_id)


class OrderRequest(BaseModel):
    book_id: str
    quantity: int = Field(ge=1, description="Copies to buy, 1 or more")
    customer_name: str = Field(min_length=1)


@app.post("/api/orders", status_code=201)
def api_create_order(req: OrderRequest):
    return service.purchase_book(req.book_id, req.quantity, req.customer_name)


@app.get("/api/orders")
def api_list_orders():
    return service.list_orders()


@app.get("/api/health")
def api_health():
    return {"status": "ok", "service": "bookstore", "mcp": "/mcp"}


# --- UI ------------------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


# --- MCP ----------------------------------------------------------------------------------
# Mounted LAST, at "/". FastAPI tries routes in order, so everything above wins
# first and only /mcp falls through to the MCP app.
app.mount("/", mcp_app)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT)
