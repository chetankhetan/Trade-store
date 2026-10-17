from sqlmodel import create_engine, Session
from typing import Optional

def get_engine(db_url: Optional[str] = None):
    if db_url:
        url = db_url
    else:
        url = "sqlite:///./trade_store.db"
    # check_same_thread False for SQLite + FastAPI
    engine = create_engine(url, echo=False, connect_args={"check_same_thread": False})
    return engine


_engine = get_engine()

def init_db(db_url: Optional[str] = None):
    global _engine
    if db_url:
        _engine = get_engine(db_url)
    from app.models import SQLModel
    SQLModel.metadata.create_all(_engine)

def get_session():
    return Session(_engine)
