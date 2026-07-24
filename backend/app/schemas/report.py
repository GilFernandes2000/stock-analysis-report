from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ScreenerStockRow(BaseModel):
    ticker: str
    company: str | None = None
    sector: str | None = None
    price: str | None = None
    change: str | None = None
    market_cap: str | None = None
    extra: dict[str, str] = {}


class ScreenerResponse(BaseModel):
    preset: str
    label: str
    description: str
    count: int
    stocks: list[ScreenerStockRow]
    stale: bool = False


class ReportSummary(BaseModel):
    id: int
    kind: str = "market"
    report_type: str
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportDetail(BaseModel):
    id: int
    kind: str = "market"
    report_type: str
    title: str
    content_json: dict[str, Any]
    content_markdown: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportGenerateRequest(BaseModel):
    report_types: list[str] | None = None
