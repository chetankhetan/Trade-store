from app.database import init_db, get_engine
from app import main
from app.models import Trade

from fastapi.testclient import TestClient
from datetime import date, timedelta
import os

client = TestClient(main.app)

def setup_module(module):
    # Use a test database file in async sqlite form
    import asyncio
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
        "expired": False
    }
    r = client.post('/trades', json=payload)
    assert r.status_code == 400
    assert "Maturity date" in r.json()['detail']

def test_store_and_replace_same_version():
    payload = {
        "trade_id": "T2",
        "version": 1,
        "counter_party_id": "CP-1",
        "book_id": "B1",
        "maturity_date": str(date.today() + timedelta(days=10)),
        "created_date": str(date.today()),
        "expired": False
    }
    r = client.post('/trades', json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data['trade_id'] == 'T2'

    # send same version with different counter party -> should replace
    payload['counter_party_id'] = 'CP-2'
    r2 = client.post('/trades', json=payload)
    assert r2.status_code == 200
    assert r2.json()['counter_party_id'] == 'CP-2'

def test_reject_lower_version():
    # existing T2 version 1; send version 0 should be rejected
    payload = {
        "trade_id": "T2",
        "version": 0,
        "counter_party_id": "CP-3",
        "book_id": "B1",
        "maturity_date": str(date.today() + timedelta(days=10)),
        "created_date": str(date.today()),
        "expired": False
    }
    r = client.post('/trades', json=payload)
    assert r.status_code == 400
    assert "lower" in r.json()['detail']

def test_expiration_job_marks_expired():
    # create a trade with maturity yesterday
    # since creation rejects past maturity, create with future then mutate DB for test
    payload2 = {
        "trade_id": "T3",
        "version": 1,
        "counter_party_id": "CP-1",
        "book_id": "B1",
        "maturity_date": str(date.today() + timedelta(days=5)),
        "created_date": str(date.today()),
        "expired": False
    }
    r = client.post('/trades', json=payload2)
    assert r.status_code == 200

    # Now directly manipulate DB to set maturity in past for test
    from app.database import get_session
    s = get_session()
    # Use raw SQL to update date (sqlite)
    d = str(date.today() - timedelta(days=1))
    s.exec("UPDATE trade SET maturity_date = :d WHERE trade_id='T3'", params={"d": d})
    s.commit()

    # trigger expiration
    resp = client.post('/admin/expire')
    assert resp.status_code == 200
    assert resp.json()['expired_count'] >= 1
