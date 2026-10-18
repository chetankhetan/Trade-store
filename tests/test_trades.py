import os
from datetime import date, timedelta
import pytest
import pytest_asyncio 
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app import main
from app.database import init_db, get_session, get_session_ctx

from unittest.mock import AsyncMock, patch
from async_asgi_testclient import TestClient as ASGITestClient

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
    assert "Maturity date" in r.json()["message"]
    assert r.json()["error"] == "MaturityError"

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
    assert "is lower than existing" in r.json()["message"]
    assert r.json()["error"] == "VersionError"

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

async def test_application_lifespan_starts_scheduler():
    """
    Verifies that booting the FastAPI application triggers the lifespan hook,
    spins up the APScheduler engine, and shuts it down cleanly at completion.
    """
    # Patch the scheduler methods to see if they get called on startup/shutdown
    with patch("app.main.AsyncIOScheduler.start") as mock_start, \
         patch("app.main.AsyncIOScheduler.shutdown") as mock_shutdown:
         
        # ASGITestClient triggers the lifespan __enter__ and __exit__ blocks automatically
        async with ASGITestClient(main.app) as test_client:
            # Assert that the scheduler was commanded to start running
            mock_start.assert_called_once()
            
        # Assert that exiting the context block commands the scheduler to shutdown safely
        mock_shutdown.assert_called_once()

async def test_scheduled_job_execution_logic():
    """
    Executes the underlying scheduled function directly to verify that the
    background task can independently grab database sessions and run without errors.
    """
    # Mock the underlying crud worker so we aren't dependent on database states for this unit test
    with patch("app.crud.update_expired_trades", new_callable=AsyncMock) as mock_update:
        mock_update.return_return_value = 5  # Mock that 5 records were updated
        
        # Manually trigger the scheduled job function
        await main.scheduled_expiration_job()
        
        # Verify the background job successfully checked out the session and talked to the CRUD layer
        mock_update.assert_called_once()