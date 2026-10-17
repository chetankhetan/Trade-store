from datetime import date
from sqlmodel import select
from app.models import Trade
from app.database import get_session
from typing import List

class VersionError(Exception):
    pass

class MaturityError(Exception):
    pass

def store_trade(trade: Trade) -> Trade:
    session = get_session()
    today = date.today()
    if trade.maturity_date < today:
        raise MaturityError("Maturity date is before today")

    # find existing highest version for this trade_id
    stmt = select(Trade).where(Trade.trade_id == trade.trade_id).order_by(Trade.version.desc())
    existing = session.exec(stmt).first()
    if existing:
        if trade.version < existing.version:
            raise VersionError(f"Incoming version {trade.version} is lower than existing {existing.version}")
        elif trade.version == existing.version:
            # replace: update existing
            existing.counter_party_id = trade.counter_party_id
            existing.book_id = trade.book_id
            existing.maturity_date = trade.maturity_date
            existing.created_date = trade.created_date
            existing.expired = trade.expired
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing
        else:
            # higher version: insert
            session.add(trade)
            session.commit()
            session.refresh(trade)
            return trade
    else:
        session.add(trade)
        session.commit()
        session.refresh(trade)
        return trade

def list_trades() -> List[Trade]:
    session = get_session()
    stmt = select(Trade)
    return list(session.exec(stmt))

def get_trades_by_id(trade_id: str) -> List[Trade]:
    session = get_session()
    stmt = select(Trade).where(Trade.trade_id == trade_id).order_by(Trade.version.desc())
    return list(session.exec(stmt))

def update_expired_trades() -> int:
    session = get_session()
    today = date.today()
    stmt = select(Trade).where(Trade.maturity_date < today).where(Trade.expired == False)
    rows = list(session.exec(stmt))
    for r in rows:
        r.expired = True
        session.add(r)
    session.commit()
    return len(rows)
