from typing import Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from contextlib import asynccontextmanager
from app.config import settings
import sys

# default to sqlite async for quick local runs; you can pass a DB URL to init_db()
DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./trade_store.db"

_engine: Optional[AsyncEngine] = None
_async_session = None

def _create_async_engine(db_url: str):
    if "sqlite" in db_url:
       return create_async_engine(db_url, echo=False, future=True)
    else: 
       return create_async_engine(db_url, pool_size=4, echo=False, future=True)

async def init_db(db_url: Optional[str] = None):
    """
    Initialize the DB and create tables. Call this once on startup.
    """
    global _engine, _async_session
    url = db_url or DEFAULT_DATABASE_URL
    _engine = _create_async_engine(url)
    # sessionmaker for AsyncSession
    _async_session = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    
    # Only allow structural table creation inside an active pytest execution run
    if "pytest" in sys.modules:
        async with _engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
    else:
        print("[Database] Skipping automatic table creation (Not in a Test environment).")
            
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Standard dependency for FastAPI.
    """
    global _async_session
    if _async_session is None:
        await init_db(settings.DATABASE_URL)
    async with _async_session() as session:
        try:
            yield session
        except:
            await session.rollback()
            raise
        finally:
            await session.close()
            
#context manager helper for non-FastAPI code blocks (like tests)
@asynccontextmanager
async def get_session_ctx() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session