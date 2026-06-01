from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.holding import Holding
from app.schemas.portfolio import (
    HoldingCreate,
    HoldingResponse,
    HoldingUpdate,
    PortfolioInsightsResponse,
)
from app.services.currency_service import CurrencyService
from app.services.portfolio import PortfolioService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=list[HoldingResponse])
def list_holdings(db: Session = Depends(get_db)):
    return db.query(Holding).order_by(Holding.ticker).all()


@router.post("", response_model=HoldingResponse, status_code=201)
def create_holding(body: HoldingCreate, db: Session = Depends(get_db)):
    holding = Holding(
        ticker=body.ticker.upper().strip(),
        shares=body.shares,
        avg_cost=body.avg_cost,
        notes=body.notes,
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return holding


@router.put("/{holding_id}", response_model=HoldingResponse)
def update_holding(
    holding_id: int, body: HoldingUpdate, db: Session = Depends(get_db)
):
    holding = db.query(Holding).filter(Holding.id == holding_id).first()
    if not holding:
        raise HTTPException(status_code=404, detail="Holding not found")

    if body.shares is not None:
        holding.shares = body.shares
    if body.avg_cost is not None:
        holding.avg_cost = body.avg_cost
    if body.notes is not None:
        holding.notes = body.notes

    db.commit()
    db.refresh(holding)
    return holding


@router.delete("/{holding_id}", status_code=204)
def delete_holding(holding_id: int, db: Session = Depends(get_db)):
    holding = db.query(Holding).filter(Holding.id == holding_id).first()
    if not holding:
        raise HTTPException(status_code=404, detail="Holding not found")
    db.delete(holding)
    db.commit()


@router.get("/insights", response_model=PortfolioInsightsResponse)
def portfolio_insights(
    currency: str = Query(default=settings.default_display_currency),
    db: Session = Depends(get_db),
):
    try:
        display = CurrencyService(db).validate_display_currency(currency)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    service = PortfolioService(db)
    try:
        return service.get_insights(display_currency=display)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
