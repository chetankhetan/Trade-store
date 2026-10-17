# app/main.py
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.models import Trade
from app import crud
from app.database import init_db, get_session  # get_session is async context manager

app = FastAPI(title="Trade Store API (async DB)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    # initialize DB (async). Optionally pass a DB URL as needed.
    await init_db()
    
@app.get("/")
def read_root():
    return {"message": "Application started successfully"}

@app.post("/trades", response_model=Trade)
async def create_trade(trade: Trade, session = Depends(get_session)):
    try:
        created = await crud.store_trade(trade, session)
        return created
    except crud.MaturityError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except crud.VersionError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/trades", response_model=list[Trade])
async def get_trades(session = Depends(get_session)):
    return await crud.list_trades(session)

@app.get("/trades/{trade_id}", response_model=list[Trade])
async def get_trade(trade_id: str, session = Depends(get_session)):
    return await crud.get_trades_by_id(trade_id, session)

@app.post("/admin/expire")
async def expire_trades(session = Depends(get_session)):
    count = await crud.update_expired_trades(session)
    return {"expired_count": count}