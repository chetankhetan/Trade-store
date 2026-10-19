from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import get_session, get_session_ctx
from app.models import Trade
from app.exceptions import TradeError
from app import crud

# BACKGROUND LIFESPAN CONFIGURATION
async def scheduled_expiration_job():
    """
    Background worker that runs at midnight. 
    It requests an isolated database session block directly since it operates 
    outside of an HTTP request context.
    """
    print("[Background Job] Starting daily trade expiration check...")
    try:
        async with get_session_ctx() as session:
            count = await crud.update_expired_trades(session)
            print(f"[Background Job] Success! Marked {count} trades as expired.")
    except Exception as e:
        print(f"[Background Job] ERROR: Failed to run automatic expiration: {e}")

# Manage the Scheduler Lifecycle using FastAPI Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the Async scheduler wrapper
    scheduler = AsyncIOScheduler()
    
    # Schedule the task using a CRON trigger (Runs at 00:00 / midnight every single day)
    scheduler.add_job(
        scheduled_expiration_job,
        trigger=CronTrigger(hour=0, minute=0),
        id="daily_trade_expiry",
        replace_existing=True
    )
    
    # Start the background worker threads
    scheduler.start()
    print("[Scheduler] Background worker engine started successfully.")
    
    yield  # The app runs its lifecycle here while the background jobs loop
    
    # Shutdown gracefully when the API app stops running
    scheduler.shutdown()
    print("[Scheduler] Background worker engine stopped.")

# Initialize FastAPI with Lifespan management
app = FastAPI(title="Trade Store API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], #tighten down as per allowed url's
    allow_credentials=False,  # Changed to True to allow specific url's
    allow_methods=["*"],
    allow_headers=["*"],
)

# CENTRAL EXCEPTION HANDLER
@app.exception_handler(TradeError)
async def trade_error_handler(request: Request, exc: TradeError):
    """
    Catches any exception inheriting from TradeError app-wide 
    and automatically transforms it into a standardized JSON API response.
    """
    return JSONResponse(
        status_code=getattr(exc, "status_code", 400),
        content={
            "error": exc.__class__.__name__,  # Dynamically extracts 'VersionError', 'MaturityError', etc.
            "message": str(exc)
        }
    )

@app.get("/")
def read_root():
    return {"message": "Application started successfully"}

@app.post("/trades", response_model=Trade, status_code=status.HTTP_200_OK)
async def create_or_update_trade(trade: Trade, session: AsyncSession = Depends(get_session)):
    # If store_trade raises VersionError or MaturityError, FastAPI catches it globally above.
    return await crud.store_trade(trade, session)

@app.get("/trades/{trade_id}", response_model=List[Trade])
async def get_trades_by_id(trade_id: str, session: AsyncSession = Depends(get_session)):
    return await crud.get_trades_by_id(trade_id, session)

@app.post("/admin/expire", status_code=status.HTTP_200_OK)
async def expire_trades(session: AsyncSession = Depends(get_session)):
    count = await crud.update_expired_trades(session)
    return {"status": "success", "expired_count": count}
