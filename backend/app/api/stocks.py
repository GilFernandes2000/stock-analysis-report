from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.stock import StockAnalysisResponse
from app.services.stock_analysis import StockAnalysisService

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/{ticker}", response_model=StockAnalysisResponse)
def get_stock_analysis(ticker: str, db: Session = Depends(get_db)):
    service = StockAnalysisService(db)
    try:
        return service.analyze(ticker)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
