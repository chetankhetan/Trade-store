from datetime import date
from sqlmodel import SQLModel, Field
from typing import Optional
from pydantic import field_validator  

class Trade(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    trade_id: str = Field(index=True)
    version: int
    counter_party_id: str
    book_id: str
    maturity_date: date
    created_date: date = Field(default_factory=date.today)
    expired: bool = False
    
    @field_validator("maturity_date", "created_date", mode="before")
    @classmethod
    def parse_dates(cls, value):
        if isinstance(value, str):
            # Formats like "2026-10-17" or "2026-10-17T00:00:00"
            return datetime.fromisoformat(value.replace("Z", "")).date()
        return value
