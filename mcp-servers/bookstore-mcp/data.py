"""Seed data for the bookstore.

Plain Python dicts, no database. `service.py` copies this list at start-up,
so edits made through the API (stock going down) live only in memory and
reset when the server restarts. Prices are in INR.
"""

BOOKS = [
    {"id": "b1", "title": "The Pragmatic Programmer", "author": "Andrew Hunt, David Thomas",
     "year": 1999, "genre": "Software", "price": 2499.0, "stock": 5},
    {"id": "b2", "title": "Clean Code", "author": "Robert C. Martin",
     "year": 2008, "genre": "Software", "price": 2199.0, "stock": 3},
    {"id": "b3", "title": "Designing Data-Intensive Applications", "author": "Martin Kleppmann",
     "year": 2017, "genre": "Software", "price": 3299.0, "stock": 2},
    {"id": "b4", "title": "The Phoenix Project", "author": "Gene Kim, Kevin Behr, George Spafford",
     "year": 2013, "genre": "DevOps", "price": 1599.0, "stock": 4},
    {"id": "b5", "title": "Site Reliability Engineering", "author": "Betsy Beyer et al.",
     "year": 2016, "genre": "DevOps", "price": 2899.0, "stock": 0},   # out of stock on purpose
    {"id": "b6", "title": "Accelerate", "author": "Nicole Forsgren, Jez Humble, Gene Kim",
     "year": 2018, "genre": "DevOps", "price": 1799.0, "stock": 6},
    {"id": "b7", "title": "Thinking, Fast and Slow", "author": "Daniel Kahneman",
     "year": 2011, "genre": "Psychology", "price": 899.0, "stock": 10},
    {"id": "b8", "title": "Sapiens", "author": "Yuval Noah Harari",
     "year": 2011, "genre": "History", "price": 699.0, "stock": 8},
    {"id": "b9", "title": "Dune", "author": "Frank Herbert",
     "year": 1965, "genre": "Science Fiction", "price": 549.0, "stock": 7},
    {"id": "b10", "title": "The Hitchhiker's Guide to the Galaxy", "author": "Douglas Adams",
     "year": 1979, "genre": "Science Fiction", "price": 399.0, "stock": 1},
]
