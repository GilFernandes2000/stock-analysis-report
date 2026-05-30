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
    date: str | None = None


class InsiderTrade(BaseModel):
    insider: str | None = None
    relationship: str | None = None
    transaction: str | None = None
    shares: str | None = None
    value: str | None = None
    date: str | None = None


class StockAnalysisResponse(BaseModel):
    ticker: str
    company: str | None = None
    sector: str | None = None
    industry: str | None = None
    price: float | None = None
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
    raw: dict[str, Any] = Field(default_factory=dict)
    stale: bool = False
    disclaimer: str = (
        "Data sourced from Finviz and is delayed 15-20 minutes. "
        "Not intended for live trading."
    )
