# Trade Store

This project implements a Trade Store REST API in Python using FastAPI and SQLModel (SQLite). It follows TDD with pytest and includes a CI workflow that runs unit tests and a vulnerability scan.

Run locally:

1. Install dependencies:

   pip install -r requirements.txt

2. Start the app:

   uvicorn app.main:app --reload

Run tests:

   pytest -q

Notes:
- The store validates trade versions and maturity dates.
- Use the /admin/expire endpoint to trigger marking expired trades.
