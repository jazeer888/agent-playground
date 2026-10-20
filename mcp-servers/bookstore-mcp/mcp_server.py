"""The MCP side of the bookstore: tools and one resource for AI agents.

Each tool is a thin wrapper around a function in service.py. The docstring of
a tool is what the agent reads to decide when to call it, so write docstrings
for the agent, not for yourself.

Tools vs resources, in one line each:
  - A TOOL does something when called (search, buy). The agent decides when.
  - A RESOURCE is content the agent (or its host app) can read for context,
    addressed by a URI, like a file. It should not change anything.

Note on the SDK: this uses `mcp` 2.x, where the class formerly called
`FastMCP` is named `MCPServer`. Same idea, new name.

Run this file directly for the stdio transport (what Claude Desktop uses):
    python mcp_server.py
For HTTP, app.py mounts `mcp.streamable_http_app()` at /mcp instead.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

import service

mcp = MCPServer(
    name="bookstore",
    instructions=(
        "A small bookstore. Use search_books or list_books to find a book id, "
        "get_book for details, then purchase_book to order. Prices are in INR."
    ),
)


def _fail(e: service.ServiceError) -> ToolError:
    """ServiceError -> ToolError. The agent receives the message as an error
    result (isError=true) instead of a crash, so it can recover or tell the user."""
    return ToolError(f"{e.code}: {e}")


# --- tools -----------------------------------------------------------------------------


@mcp.tool()
def list_books() -> list[dict]:
    """List every book in the store with id, title, author, price (INR) and stock."""
    return service.list_books()


@mcp.tool()
def search_books(query: str) -> list[dict]:
    """Find books whose title or author contains the query (case-insensitive).
    Returns an empty list when nothing matches."""
    return service.search_books(query)


@mcp.tool()
def get_book(book_id: str) -> dict:
    """Full details of one book by its id (for example 'b3')."""
    try:
        return service.get_book(book_id)
    except service.ServiceError as e:
        raise _fail(e)


@mcp.tool()
def purchase_book(book_id: str, quantity: int, customer_name: str) -> dict:
    """Buy `quantity` copies of a book for `customer_name`. Reduces stock and
    returns the order with its order_id and total. Fails if the book does not
    exist, the quantity is below 1, or there is not enough stock."""
    try:
        return service.purchase_book(book_id, quantity, customer_name)
    except service.ServiceError as e:
        raise _fail(e)


@mcp.tool()
def list_orders() -> list[dict]:
    """All orders placed since the server started, oldest first."""
    return service.list_orders()


# --- resource ----------------------------------------------------------------------------


@mcp.resource("bookstore://catalog", name="catalog", mime_type="text/plain",
              description="The whole catalog as plain text, one book per line.")
def catalog() -> str:
    return service.catalog_text()


if __name__ == "__main__":
    # stdio: the client starts this process and talks over stdin/stdout.
    # Never print() in this mode; stdout belongs to the protocol.
    mcp.run(transport="stdio")
