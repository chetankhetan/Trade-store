from fastapi.testclient import TestClient
from datetime import date, timedelta
import os
import asyncio

from app import main
from app.database import init_db, get_session

client = TestClient(main.app)


def setup_module(module):
    # Initialize async test DB using aiosqlite URL
    asyncio.run(init_db("sqlite+aiosqlite:///./test_trade_store.db"))


def teardown_module(module):
    try:
        os.remove("./test_trade_store.db")
    except OSError:
        pass


def test_reject_past_maturity():
    payload = {
        "trade_id": "T1",
        "version": 1,
        "counter_party_id": "CP-1",
        "book_id": "B1",
        "maturity_date": str(date.today() - timedelta(days=1)),
        "created_date": str(date.today()),
        "expired": False,
    }
    r = client.post("/trades", json=payload)
    assert r.status_code == 400
    assert "Maturity date" in r.json()["detail"]


def test_store_and_replace_same_version():
    payload = {
        "trade_id": "T2",
        "version": 1,
        "counter_party_id": "CP-1",
        "book_id": "B1",
        "maturity_date": str(date.today() + timedelta(days=10)),
        "created_date": str(date.today()),
        "expired": False,
    }
    r = client.post("/trades", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["trade_id"] == "T2"

    # send same version with different counter party -> should replace
    payload["counter_party_id"] = "CP-2"
    r2 = client.post("/trades", json=payload)
    assert r2.status_code == 200
    assert r2.json()["counter_party_id"] == "CP-2"


def test_reject_lower_version():
    # existing T2 version 1; send version 0 should be rejected
    payload = {
        "trade_id": "T2",
        "version": 0,
        "counter_party_id": "CP-3",
        "book_id": "B1",
        "maturity_date": str(date.today() + timedelta(days=10)),
        "created_date": str(date.today()),
        "expired": False,
    }
    r = client.post("/trades", json=payload)
    assert r.status_code == 400
    assert "lower" in r.json()["detail"]


def test_expiration_job_marks_expired():
    # create a trade with a future maturity (we'll mutate it to past via async session)
    payload = {
        "trade_id": "T3",
        "version": 1,
        "counter_party_id": "CP-1",
        "book_id": "B1",
        "maturity_date": str(date.today() + timedelta(days=5)),
        "created_date": str(date.today()),
        "expired": False,
    }
    r = client.post("/trades", json=payload)
    assert r.status_code == 200

    # Now set the maturity to yesterday using async session
    async def set_maturity_past():
        d = str(date.today() - timedelta(days=1))
        async with get_session() as s:
            from sqlalchemy import text

            await s.execute(text("UPDATE trade SET maturity_date = :d WHERE trade_id = 'T3'"), {"d": d})
            await s.commit()

    asyncio.run(set_maturity_past())

    # trigger expiration
    resp = client.post("/admin/expire")
    assert resp.status_code == 200
    assert resp.json()["expired_count"] >= 1