import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.schemas.stock import StockAnalysisResponse
from app.services.auth import get_current_user
from app.services.currency_service import CurrencyService
from app.services.stock_analysis import StockAnalysisService
from app.services.ticker_symbols import is_valid_ticker, normalize_ticker

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/stocks", tags=["stocks"], dependencies=[Depends(get_current_user)]
)


@router.get("/meta/examples")
def ticker_examples():
    from app.services.ticker_symbols import EU_EXCHANGE_SUFFIXES, EU_TICKER_ALIASES

    return {
        "us_examples": ["AAPL", "MSFT", "NVDA"],
        "europe_examples": ["SAP.DE", "ASML.AS", "VOD.L", "MC.PA", "NESN.SW", "BMW.DE"],
        "exchange_suffixes": list(EU_EXCHANGE_SUFFIXES),
        "aliases": EU_TICKER_ALIASES,
        "hint": (
            "US stocks use plain tickers (AAPL). European local listings use "
            "exchange suffixes: .DE Germany, .L London, .PA Paris, .AS Amsterdam, .SW Switzerland."
        ),
    }


@router.get("/{ticker}", response_model=StockAnalysisResponse)
def get_stock_analysis(
    ticker: str,
    currency: str = Query(default=settings.default_display_currency),
    db: Session = Depends(get_db),
):
    ticker = normalize_ticker(ticker)
    if not is_valid_ticker(ticker):
        raise HTTPException(
            status_code=400,
            detail="Invalid ticker. Use symbols like AAPL, SAP.DE, ASML.AS, VOD.L, MC.PA",
        )
    try:
        display = CurrencyService(db).validate_display_currency(currency)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    service = StockAnalysisService(db)
    try:
        return service.analyze(ticker, display_currency=display)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("Stock analysis for '%s' failed: %s", ticker, exc)
        raise HTTPException(
            status_code=502, detail="Upstream market data is unavailable right now."
        ) from exc
