import os
from datetime import date, timedelta
import pytest
import pytest_asyncio 
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app import main
from app.database import init_db, get_session, get_session_ctx

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio(loop_scope="module") 

DATABASE_URL = "sqlite+aiosqlite:///./test_trade_store.db"

# 1. Setup and Teardown using an async pytest fixture
@pytest_asyncio.fixture(scope="module", autouse=True, loop_scope="module")
async def setup_test_database():
    await init_db(DATABASE_URL)
    
    # Override FastAPI dependency to force your endpoints to use the test database session
    main.app.dependency_overrides[get_session] = get_session
    
    yield
    
    # Clean up overrides after tests finish
    main.app.dependency_overrides.clear()
    try:
        if os.path.exists("./test_trade_store.db"):
            os.remove("./test_trade_store.db")
    except OSError:
        pass

# 2. Provide a clean AsyncClient for every test
@pytest_asyncio.fixture(loop_scope="module")
async def client():
    # Use ASGITransport to pipe httpx requests directly into the FastAPI app safely
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

async def test_reject_past_maturity(client):
    payload = {
        "trade_id": "T1",
        "version": 1,
        "counter_party_id": "CP-1",
        "book_id": "B1",
        "maturity_date": (date.today() - timedelta(days=1)).isoformat(),
        "created_date": date.today().isoformat(),
        "expired": False,
    }
    r = await client.post("/trades", json=payload)
    assert r.status_code == 400
    assert "Maturity date" in r.json()["detail"]

async def test_store_and_replace_same_version(client):
    payload = {
        "trade_id": "T2",
        "version": 1,
        "counter_party_id": "CP-1",
        "book_id": "B1",
        "maturity_date": str(date.today() + timedelta(days=10)),
        "created_date": str(date.today()),
        "expired": False,
    }
    r = await client.post("/trades", json=payload)
    assert r.status_code == 200
    assert r.json()["trade_id"] == "T2"

    # Send same version with different counter party -> should replace
    payload["counter_party_id"] = "CP-2"
    r2 = await client.post("/trades", json=payload)
    assert r2.status_code == 200
    assert r2.json()["counter_party_id"] == "CP-2"

async def test_reject_lower_version(client):
    # T2 version 1 already exists from the previous test structure
    payload = {
        "trade_id": "T2",
        "version": 0,
        "counter_party_id": "CP-3",
        "book_id": "B1",
        "maturity_date": str(date.today() + timedelta(days=10)),
        "created_date": str(date.today()),
        "expired": False,
    }
    r = await client.post("/trades", json=payload)
    assert r.status_code == 400
    assert "lower" in r.json()["detail"]

async def test_expiration_job_marks_expired(client):
    payload = {
        "trade_id": "T3",
        "version": 1,
        "counter_party_id": "CP-1",
        "book_id": "B1",
        "maturity_date": str(date.today() + timedelta(days=5)),
        "created_date": str(date.today()),
        "expired": False,
    }
    r = await client.post("/trades", json=payload)
    assert r.status_code == 200

    # Clean execution on the shared event loop context
    past_date = str(date.today() - timedelta(days=1))
    async with get_session_ctx() as s:
        # Note: If your model sets __tablename__ = "trade", use that name here
        await s.execute(
            text("UPDATE TRADE SET maturity_date = :d WHERE trade_id = 'T3'"), 
            {"d": past_date}
        )
        await s.commit()

    # trigger expiration
    resp = await client.post("/admin/expire")
    assert resp.status_code == 200
    assert resp.json()["expired_count"] >= 1
