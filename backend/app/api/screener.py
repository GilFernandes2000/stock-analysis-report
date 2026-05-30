from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import SCREENER_PRESETS
from app.database import get_db
from app.schemas.report import ScreenerResponse, ScreenerStockRow
from app.services.finviz_client import FinvizService

router = APIRouter(prefix="/screener", tags=["screener"])


@router.get("/presets")
def list_presets():
    return {
        name: {"label": cfg["label"], "description": cfg["description"]}
        for name, cfg in SCREENER_PRESETS.items()
    }


@router.get("/{preset}", response_model=ScreenerResponse)
def run_screener(preset: str, db: Session = Depends(get_db)):
    if preset not in SCREENER_PRESETS:
        raise HTTPException(status_code=404, detail=f"Unknown preset: {preset}")

    config = SCREENER_PRESETS[preset]
    service = FinvizService(db)

    try:
        rows, stale = service.run_screener(preset)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    stocks = []
    for row in rows:
        ticker = row.get("Ticker", "")
        extra = {k: v for k, v in row.items() if k not in ("Ticker", "Company", "Price", "Change", "Market Cap", "Sector")}
        stocks.append(
            ScreenerStockRow(
                ticker=ticker,
                company=row.get("Company"),
                sector=row.get("Sector"),
                price=row.get("Price"),
                change=row.get("Change"),
                market_cap=row.get("Market Cap"),
                extra=extra,
            )
        )

    return ScreenerResponse(
        preset=preset,
        label=config["label"],
        description=config["description"],
        count=len(stocks),
        stocks=stocks,
        stale=stale,
    )
