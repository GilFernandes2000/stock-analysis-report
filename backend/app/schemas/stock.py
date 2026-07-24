from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TrendAnalysis(BaseModel):
    score: int
    label: str  # Bullish, Neutral, Bearish
    signals: list[str]


class NewsItem(BaseModel):
    title: str
    url: str | None = None
    date: str | None = None
    sentiment: str | None = None
    compound_score: float | None = None


class SentimentSummary(BaseModel):
    label: str
    average_compound: float
    positive_count: int
    negative_count: int
    neutral_count: int
    headlines: list[NewsItem]


class AnalystTarget(BaseModel):
    analyst: str | None = None
    price_target: float | None = None
    native_price_target: float | None = None
    date: str | None = None


class InsiderTrade(BaseModel):
    insider: str | None = None
    relationship: str | None = None
    transaction: str | None = None
    shares: str | None = None
    value: str | None = None
    date: str | None = None


class InsiderSignal(BaseModel):
    """Scored read on recent insider filings (open-market buys vs sales)."""

    label: str  # Bullish | Neutral | Bearish | No activity
    score: int
    window_days: int
    buy_count: int
    sell_count: int
    buyers: int
    sellers: int
    buy_value: float
    sell_value: float
    net_value: float
    signals: list[str] = Field(default_factory=list)
    summary: str = ""


class StockAnalysisResponse(BaseModel):
    ticker: str
    company: str | None = None
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    exchange: str | None = None
    currency: str | None = None  # display currency (backward compatible)
    native_currency: str | None = None
    native_price: float | None = None
    display_currency: str = "EUR"
    display_price: float | None = None
    currency_note: str | None = None
    data_source: str = "finviz"
    price: float | None = None  # same as display_price (backward compatible)
    change: str | None = None
    market_cap: str | None = None
    pe: str | None = None
    eps: str | None = None
    dividend: str | None = None
    beta: str | None = None
    rsi: float | None = None
    sma20: float | None = None
    sma50: float | None = None
    sma200: float | None = None
    inst_own: str | None = None
    insider_own: str | None = None
    short_float: str | None = None
    perf_week: str | None = None
    perf_month: str | None = None
    perf_quarter: str | None = None
    perf_ytd: str | None = None
    high_52w: str | None = None
    low_52w: str | None = None
    chart_url: str | None = None
    trend: TrendAnalysis
    sentiment: SentimentSummary
    analyst_targets: list[AnalystTarget] = Field(default_factory=list)
    analyst_upside_pct: float | None = None
    insider_trades: list[InsiderTrade] = Field(default_factory=list)
    insider_signal: InsiderSignal | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    stale: bool = False
    disclaimer: str = (
        "Data sourced from Finviz and/or Yahoo Finance and may be delayed. "
        "Not intended for live trading."
    )
