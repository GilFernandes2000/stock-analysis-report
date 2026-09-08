from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.favorite import Favorite
from app.models.user import User
from app.schemas.favorite import (
    FavoriteCreate,
    FavoriteResponse,
    QuotesResponse,
)
from app.services.auth import get_current_user
from app.services.currency_service import CurrencyService
from app.services.quotes import QuoteService
from app.services.ticker_symbols import is_valid_ticker, normalize_ticker

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("", response_model=list[FavoriteResponse])
def list_favorites(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Favorite)
        .filter(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc())
        .all()
    )
    return [FavoriteResponse.model_validate(r) for r in rows]


@router.post("", response_model=FavoriteResponse, status_code=201)
def add_favorite(
    payload: FavoriteCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticker = normalize_ticker(payload.ticker)
    if not is_valid_ticker(ticker):
        raise HTTPException(status_code=422, detail=f"Invalid ticker: {payload.ticker}")

    existing = (
        db.query(Favorite)
        .filter(Favorite.user_id == user.id, Favorite.ticker == ticker)
        .first()
    )
    if existing:
        return FavoriteResponse.model_validate(existing)

    favorite = Favorite(user_id=user.id, ticker=ticker, note=payload.note)
    db.add(favorite)
    db.commit()
    db.refresh(favorite)
    return FavoriteResponse.model_validate(favorite)


@router.delete("/{ticker}", status_code=204)
def remove_favorite(
    ticker: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    normalized = normalize_ticker(ticker)
    if not is_valid_ticker(normalized):
        raise HTTPException(status_code=422, detail=f"Invalid ticker: {ticker}")
    deleted = (
        db.query(Favorite)
        .filter(
            Favorite.user_id == user.id,
            Favorite.ticker == normalized,
        )
        .delete()
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Favorite not found")
    db.commit()


@router.get("/quotes", response_model=QuotesResponse)
def favorite_quotes(
    currency: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    display = CurrencyService(db).validate_display_currency(
        currency or settings.default_display_currency
    )
    tickers = [
        f.ticker
        for f in db.query(Favorite).filter(Favorite.user_id == user.id).all()
    ]
    quotes, stale = QuoteService(db).get_quotes(tickers, display)
    # Preserve the user's most-recent-first ordering from the favorites list
    order = {t: i for i, t in enumerate(tickers)}
    quotes.sort(key=lambda q: order.get(q.ticker, 0))
    return QuotesResponse(display_currency=display, quotes=quotes, stale=stale)
