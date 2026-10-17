from fastapi import FastAPI, HTTPException
from app.models import Trade
from app.database import init_db
from app import crud
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Trade Store API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()
    
@app.get("/")
def read_root():
    return {"message": "This is home page. Application started successfully"}

@app.post('/trades', response_model=Trade)
def create_trade(trade: Trade):
    try:
        created = crud.store_trade(trade)
        return created
    except crud.MaturityError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except crud.VersionError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get('/trades', response_model=list[Trade])
def get_trades():
    return crud.list_trades()

@app.get('/trades/{trade_id}', response_model=list[Trade])
def get_trade(trade_id: str):
    return crud.get_trades_by_id(trade_id)

# admin endpoint to trigger expiration (useful for tests and manual run)
@app.post('/admin/expire')
def expire_trades():
    count = crud.update_expired_trades()
    return {"expired_count": count}
