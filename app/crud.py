from datetime import date, datetime
from typing import List
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Trade
from app.exceptions import VersionError, MaturityError

async def store_trade(trade: Trade, session: AsyncSession) -> Trade:
    """
    Store a trade (async). session should be an AsyncSession provided by the dependency.
    Rules:
      - Reject if maturity_date < today
      - If existing highest version exists:
          incoming < existing -> VersionError
          incoming == existing -> replace fields on existing (update)
          incoming > existing -> insert new row (higher version)
    """
    today = date.today()
    
    # Force safety conversion for created_date
    if isinstance(trade.maturity_date, str):
        trade.maturity_date = datetime.fromisoformat(trade.maturity_date.replace("Z", "")).date()

    if isinstance(trade.created_date, str):
        trade.created_date = datetime.fromisoformat(trade.created_date.replace("Z", "")).date()

    if trade.maturity_date < today:
        raise MaturityError("Maturity date is before today")
    
    stmt = select(Trade).where(Trade.trade_id == trade.trade_id).order_by(Trade.version.desc())
    res = await session.execute(stmt)
    existing = res.scalars().first()

    if existing:
        # Extra safety fallback for existing database record properties if needed
        if isinstance(existing.maturity_date, str):
            existing.maturity_date = datetime.fromisoformat(existing.maturity_date.replace("Z", "")).date()
        if isinstance(existing.created_date, str):
            existing.created_date = datetime.fromisoformat(existing.created_date.replace("Z", "")).date()
        
        if trade.version < existing.version:
            raise VersionError(trade.version, existing.version)
        elif trade.version == existing.version:
            # Replace fields on the existing record
            existing.counter_party_id = trade.counter_party_id
            existing.book_id = trade.book_id
            existing.maturity_date = trade.maturity_date
            existing.created_date = trade.created_date
            existing.expired = trade.expired
            session.add(existing)
            await session.commit()
            await session.refresh(existing)
            return existing
        else:
            # Higher version -> insert new record
            session.add(trade)
            await session.commit()
            await session.refresh(trade)
            return trade
    else:
        session.add(trade)
        await session.commit()
        await session.refresh(trade)
        return trade

async def list_trades(session: AsyncSession) -> List[Trade]:
    res = await session.execute(select(Trade))
    return res.scalars().all()

async def get_trades_by_id(trade_id: str, session: AsyncSession) -> List[Trade]:
    stmt = select(Trade).where(Trade.trade_id == trade_id).order_by(Trade.version.desc())
    res = await session.execute(stmt)
    return res.scalars().all()

async def update_expired_trades(session: AsyncSession) -> int:
    """
    Mark trades as expired where maturity_date < today and expired == False.
    Returns number of rows updated.
    """
    today = date.today()
    stmt = select(Trade).where(Trade.maturity_date < today).where(Trade.expired == False)
    res = await session.execute(stmt)
    rows = res.scalars().all()
    for r in rows:
        r.expired = True
        session.add(r)
    if rows:
        await session.commit()
    return len(rows)