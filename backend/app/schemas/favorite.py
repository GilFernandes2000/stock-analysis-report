from datetime import datetime

from pydantic import BaseModel, Field


class FavoriteCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=32)
    note: str | None = Field(default=None, max_length=256)


class FavoriteResponse(BaseModel):
    id: int
    ticker: str
    note: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class Quote(BaseModel):
    ticker: str
    name: str | None = None
    sector: str | None = None
    country: str | None = None
    native_currency: str | None = None
    native_price: float | None = None
    display_currency: str = "EUR"
    price: float | None = None  # in display currency
    change_pct: float | None = None
    market_cap: float | None = None
    pe: float | None = None


class QuotesResponse(BaseModel):
    display_currency: str
    quotes: list[Quote]
    stale: bool = False
