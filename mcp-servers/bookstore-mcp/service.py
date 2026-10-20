"""Business logic for the bookstore. This is the ONE place rules live.

Both interfaces call these functions:
  - REST (app.py)        for humans, browsers and ordinary apps
  - MCP  (mcp_server.py) for AI agents

Neither interface knows about stock rules or order IDs. They only translate
errors: REST turns ServiceError into an HTTP status, MCP turns it into a tool
error. If you change a rule here, both interfaces change together.

State is in memory: two module-level lists. Restart the server, and it resets.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone

from data import BOOKS as SEED_BOOKS

# --- errors --------------------------------------------------------------------------
# One base class so callers can catch everything from this module in one line.
# `code` is a short machine-readable label; `status` is the HTTP status REST uses.


class ServiceError(Exception):
    code = "SERVICE_ERROR"
    status = 400


class BookNotFound(ServiceError):
    code, status = "BOOK_NOT_FOUND", 404


class InvalidQuantity(ServiceError):
    code, status = "INVALID_QUANTITY", 400


class OutOfStock(ServiceError):
    code, status = "OUT_OF_STOCK", 409   # 409 Conflict: the request clashes with current state


# --- state ---------------------------------------------------------------------------

_books: list[dict] = copy.deepcopy(SEED_BOOKS)   # a copy, so data.py stays pristine
_orders: list[dict] = []


def reset() -> None:
    """Back to the seed data. Handy in tests and demos."""
    global _books, _orders
    _books = copy.deepcopy(SEED_BOOKS)
    _orders = []


# --- queries -------------------------------------------------------------------------


def list_books() -> list[dict]:
    """Every book, including ones with zero stock (so the UI can show 'sold out')."""
    return [dict(b) for b in _books]   # copies: callers can't mutate our state by accident


def get_book(book_id: str) -> dict:
    for b in _books:
        if b["id"] == book_id:
            return dict(b)
    raise BookNotFound(f"No book with id '{book_id}'. Use list_books to see valid ids.")


def search_books(query: str) -> list[dict]:
    """Case-insensitive match on title or author. Empty query returns nothing."""
    q = query.strip().lower()
    if not q:
        return []
    return [dict(b) for b in _books if q in b["title"].lower() or q in b["author"].lower()]


# --- commands ------------------------------------------------------------------------


def purchase_book(book_id: str, quantity: int, customer_name: str) -> dict:
    """Decrements stock and records an order. Raises on every bad case.

    Checks run in this order on purpose: cheap validation first, then the
    lookup, then the stock rule. The caller gets the most specific error.
    """
    if not isinstance(quantity, int) or quantity < 1:
        raise InvalidQuantity("quantity must be a whole number of 1 or more.")
    if not customer_name or not customer_name.strip():
        raise InvalidQuantity("customer_name is required.")

    book = next((b for b in _books if b["id"] == book_id), None)   # the real dict, not a copy
    if book is None:
        raise BookNotFound(f"No book with id '{book_id}'. Use list_books to see valid ids.")
    if book["stock"] < quantity:
        raise OutOfStock(
            f"Only {book['stock']} copies of '{book['title']}' left; you asked for {quantity}."
        )

    book["stock"] -= quantity
    order = {
        "order_id": f"ord-{len(_orders) + 1:04d}",   # ord-0001, ord-0002, ...
        "book_id": book["id"],
        "title": book["title"],
        "quantity": quantity,
        "customer_name": customer_name.strip(),
        "total": round(book["price"] * quantity, 2),
        "placed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _orders.append(order)
    return dict(order)


def list_orders() -> list[dict]:
    return [dict(o) for o in _orders]


# --- a read-only view, used by the MCP resource --------------------------------------


def catalog_text() -> str:
    """The catalog as plain text: one line per book. Resources are for
    reading context, so text is the natural shape."""
    lines = ["Bookstore catalog (price in INR, stock in copies)", ""]
    for b in _books:
        lines.append(f"{b['id']:>4}  {b['title']} - {b['author']} ({b['year']})  "
                     f"{b['price']:.0f}  stock={b['stock']}")
    return "\n".join(lines)
