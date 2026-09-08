from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import MOVER_PRESETS, SCREENER_PRESETS
from app.database import get_db
from app.schemas.report import ScreenerResponse, ScreenerStockRow
from app.services.finviz_client import (
    FinvizService,
    parse_float,
    parse_percent,
    parse_market_cap,
)

router = APIRouter(prefix="/screener", tags=["screener"])

_KNOWN_KEYS = {
    "No.",
    "Ticker",
    "Company",
    "Sector",
    "Industry",
    "Country",
    "Market Cap",
    "P/E",
    "Price",
    "Change",
    "Volume",
}


def _build_row(row: dict[str, str]) -> ScreenerStockRow:
    ticker = row.get("Ticker", "")
    extra = {k: v for k, v in row.items() if k not in _KNOWN_KEYS}
    return ScreenerStockRow(
        ticker=ticker,
        company=row.get("Company"),
        sector=row.get("Sector"),
        industry=row.get("Industry"),
        country=row.get("Country"),
        price=row.get("Price"),
        change=row.get("Change"),
        market_cap=row.get("Market Cap"),
        pe=row.get("P/E"),
        volume=row.get("Volume"),
        price_value=parse_float(row.get("Price")),
        change_pct=parse_percent(row.get("Change")),
        market_cap_value=parse_market_cap(row.get("Market Cap")),
        pe_value=parse_float(row.get("P/E")),
        volume_value=parse_float(row.get("Volume")),
        extra=extra,
    )


@router.get("/presets")
def list_presets():
    return {
        name: {"label": cfg["label"], "description": cfg["description"]}
        for name, cfg in SCREENER_PRESETS.items()
    }


@router.get("/movers")
def list_movers():
    return {
        name: {"label": cfg["label"], "description": cfg["description"]}
        for name, cfg in MOVER_PRESETS.items()
    }


@router.get("/{preset}", response_model=ScreenerResponse)
def run_screener(preset: str, db: Session = Depends(get_db)):
    config = SCREENER_PRESETS.get(preset) or MOVER_PRESETS.get(preset)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Unknown preset: {preset}")

    service = FinvizService(db)
    try:
        rows, stale = service.run_screener(preset)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    stocks = [_build_row(row) for row in rows if row.get("Ticker")]
    return ScreenerResponse(
        preset=preset,
        label=config["label"],
        description=config["description"],
        count=len(stocks),
        stocks=stocks,
        stale=stale,
    )
