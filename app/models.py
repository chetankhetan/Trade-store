from datetime import date
from sqlmodel import SQLModel, Field
from typing import Optional

class Trade(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    trade_id: str = Field(index=True)
    version: int
    counter_party_id: str
    book_id: str
    maturity_date: date
    created_date: date = Field(default_factory=date.today)
    expired: bool = False
