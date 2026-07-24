from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.stock import InsiderSignal

# ---------------------------------------------------------------------------
# Portfolio CRUD
# ---------------------------------------------------------------------------


class PortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    broker: str = Field(default="manual")
    base_currency: str = Field(default="EUR", max_length=8)
    benchmark: str = Field(default="^GSPC", max_length=32)


class PortfolioUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    broker: str | None = None
    base_currency: str | None = Field(default=None, max_length=8)
    benchmark: str | None = Field(default=None, max_length=32)


class PortfolioResponse(BaseModel):
    id: int
    name: str
    broker: str
    base_currency: str
    benchmark: str
    created_at: datetime
    transaction_count: int = 0

    model_config = {"from_attributes": True}


class PortfolioSummary(PortfolioResponse):
    """Portfolio card with headline numbers for the hub page."""

    market_value: float | None = None
    total_return: float | None = None
    total_return_pct: float | None = None
    day_change_pct: float | None = None
    position_count: int = 0


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


class TransactionCreate(BaseModel):
    type: str
    date: datetime
    ticker: str | None = Field(default=None, max_length=32)
    isin: str | None = Field(default=None, max_length=16)
    name: str | None = Field(default=None, max_length=256)
    shares: float | None = None
    price: float | None = None
    currency: str | None = Field(default=None, max_length=8)
    amount: float = 0.0
    fees: float = Field(default=0.0, ge=0)
    fx_rate: float | None = None
    note: str | None = None
    external_id: str | None = Field(default=None, max_length=128)


class TransactionResponse(TransactionCreate):
    id: int
    portfolio_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Import pipeline
# ---------------------------------------------------------------------------


class ImportRow(BaseModel):
    """A parsed transaction candidate shown in the import preview."""

    type: str
    date: datetime
    ticker: str | None = None
    isin: str | None = None
    name: str | None = None
    shares: float | None = None
    price: float | None = None
    currency: str | None = None
    amount: float = 0.0
    fees: float = 0.0
    fx_rate: float | None = None
    note: str | None = None
    external_id: str | None = None
    duplicate: bool = False
    ticker_resolved: bool = True


class ImportPreviewResponse(BaseModel):
    broker: str
    file_kind: str
    rows: list[ImportRow]
    total_rows: int
    duplicate_count: int
    unresolved_isins: list[str]
    warnings: list[str]


class ImportCommitRequest(BaseModel):
    rows: list[ImportRow]
    skip_duplicates: bool = True


class ImportCommitResponse(BaseModel):
    imported: int
    skipped: int


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class PositionResponse(BaseModel):
    ticker: str
    name: str | None = None
    isin: str | None = None
    shares: float
    avg_cost: float  # per share, base currency, fees included
    cost_basis: float
    current_price: float | None = None  # base currency
    native_price: float | None = None
    native_currency: str | None = None
    market_value: float | None = None
    weight_pct: float | None = None
    unrealized_pnl: float | None = None
    unrealized_pnl_pct: float | None = None
    realized_pnl: float = 0.0
    dividends: float = 0.0
    fees: float = 0.0
    day_change_pct: float | None = None
    sector: str | None = None
    country: str | None = None
    trend_label: str | None = None
    first_bought: datetime | None = None


class ClosedPositionResponse(BaseModel):
    ticker: str
    name: str | None = None
    realized_pnl: float
    dividends: float = 0.0
    fees: float = 0.0


class AllocationSlice(BaseModel):
    label: str
    value: float
    weight_pct: float


class PerformancePoint(BaseModel):
    date: str  # ISO date
    value: float  # portfolio market value in base currency
    cost_basis: float  # cumulative net invested capital
    benchmark: float | None = None  # benchmark indexed to the same start capital
    twr_index: float | None = None  # time-weighted return index (start = 100)


class RiskMetrics(BaseModel):
    volatility_pct: float | None = None  # annualized
    sharpe: float | None = None
    max_drawdown_pct: float | None = None
    beta: float | None = None
    twr_pct: float | None = None  # time-weighted return over the full period
    benchmark_return_pct: float | None = None
    best_day_pct: float | None = None
    worst_day_pct: float | None = None


class ContributorEntry(BaseModel):
    ticker: str
    name: str | None = None
    total_pnl: float  # realized + unrealized + dividends - fees
    return_pct: float | None = None


class CashFlowSummary(BaseModel):
    deposits: float = 0.0
    withdrawals: float = 0.0
    dividends: float = 0.0
    interest: float = 0.0
    fees: float = 0.0
    taxes: float = 0.0
    invested: float = 0.0  # net buys - sells
    cash_balance: float = 0.0


class HoldingInsider(BaseModel):
    ticker: str
    name: str | None = None
    signal: InsiderSignal


class PortfolioInsiderResponse(BaseModel):
    portfolio_id: int
    as_of: datetime
    holdings: list[HoldingInsider]
    advice: list[str]
    no_data_tickers: list[str]


class PortfolioAnalyticsResponse(BaseModel):
    portfolio_id: int
    name: str
    base_currency: str
    benchmark: str
    as_of: datetime
    market_value: float
    cost_basis: float
    cash_balance: float
    total_value: float  # market value + cash
    unrealized_pnl: float
    unrealized_pnl_pct: float | None = None
    realized_pnl: float
    dividends_received: float
    fees_paid: float
    total_return: float  # unrealized + realized + dividends - fees
    total_return_pct: float | None = None
    day_change: float | None = None
    day_change_pct: float | None = None
    positions: list[PositionResponse]
    closed_positions: list[ClosedPositionResponse]
    sector_allocation: list[AllocationSlice]
    currency_allocation: list[AllocationSlice]
    country_allocation: list[AllocationSlice]
    performance: list[PerformancePoint]
    risk: RiskMetrics
    top_contributors: list[ContributorEntry]
    top_detractors: list[ContributorEntry]
    cash_flows: CashFlowSummary
    risk_flags: list[str]
    stale: bool = False
