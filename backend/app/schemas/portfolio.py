from datetime import datetime

from pydantic import BaseModel, Field


class HoldingCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=32)
    shares: float = Field(gt=0)
    avg_cost: float = Field(
        ge=0,
        description="Average cost per share in display currency (default EUR)",
    )
    notes: str | None = None


class HoldingUpdate(BaseModel):
    shares: float | None = Field(default=None, gt=0)
    avg_cost: float | None = Field(default=None, ge=0)
    notes: str | None = None


class HoldingResponse(BaseModel):
    id: int
    ticker: str
    shares: float
    avg_cost: float
    notes: str | None
    added_at: datetime

    model_config = {"from_attributes": True}


class HoldingInsight(BaseModel):
    ticker: str
    shares: float
    avg_cost: float
    current_price: float | None
    market_value: float | None
    cost_basis: float
    unrealized_pnl: float | None
    unrealized_pnl_pct: float | None
    sector: str | None
    trend_label: str
    sentiment_label: str


class SectorAllocation(BaseModel):
    sector: str
    weight_pct: float
    value: float


class PortfolioInsightsResponse(BaseModel):
    display_currency: str = "EUR"
    holdings: list[HoldingInsight]
    total_cost_basis: float
    total_market_value: float | None
    total_unrealized_pnl: float | None
    total_unrealized_pnl_pct: float | None
    sector_allocation: list[SectorAllocation]
    risk_flags: list[str]
    stale: bool = False
