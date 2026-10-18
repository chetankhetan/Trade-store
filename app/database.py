from typing import Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from contextlib import asynccontextmanager

# default to sqlite async for quick local runs; you can pass a DB URL to init_db()
DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./trade_store.db"

_engine: Optional[AsyncEngine] = None
_async_session = None

def _create_async_engine(db_url: str):
    return create_async_engine(db_url, echo=False, future=True)

async def init_db(db_url: Optional[str] = None):
    """
    Initialize the DB and create tables. Call this once on startup.
    """
    global _engine, _async_session
    url = db_url or DEFAULT_DATABASE_URL
    _engine = _create_async_engine(url)
    # sessionmaker for AsyncSession
    _async_session = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    # create tables (run sync create_all in an async context)
    async with _engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
            
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Standard dependency for FastAPI.
    Usage in routes: session: AsyncSession = Depends(get_session)
    """
    global _async_session
    if _async_session is None:
        await init_db()
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
    """
    Use this helper anywhere you want to use 'async with' manually in code.
    """
    async for session in get_session():
        yield session