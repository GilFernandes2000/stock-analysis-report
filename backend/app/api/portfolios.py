from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.portfolio import BROKERS, TRANSACTION_TYPES, Portfolio, Transaction
from app.models.user import User
from app.schemas.portfolio import (
    HoldingInsider,
    ImportCommitRequest,
    ImportCommitResponse,
    ImportPreviewResponse,
    PortfolioAnalyticsResponse,
    PortfolioCreate,
    PortfolioInsiderResponse,
    PortfolioResponse,
    PortfolioSummary,
    PortfolioUpdate,
    TransactionCreate,
    TransactionResponse,
)
from app.services.auth import get_current_user
from app.services.importers import ImportService
from app.services.portfolio_analytics import PortfolioAnalyticsService
from app.utils.time import utcnow

router = APIRouter(prefix="/portfolios", tags=["portfolios"])

# Broker CSV exports are well under this; the cap guards against a memory-DoS
# upload. A year of very active trading is a few hundred KB.
MAX_IMPORT_BYTES = 10_000_000


def _get_portfolio(db: Session, user: User, portfolio_id: int) -> Portfolio:
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


def _to_response(portfolio: Portfolio) -> PortfolioResponse:
    resp = PortfolioResponse.model_validate(portfolio)
    resp.transaction_count = len(portfolio.transactions)
    return resp


@router.get("", response_model=list[PortfolioSummary])
def list_portfolios(
    quotes: bool = Query(default=False, description="Include live valuation"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolios = (
        db.query(Portfolio)
        .filter(Portfolio.user_id == user.id)
        .order_by(Portfolio.created_at)
        .all()
    )
    service = PortfolioAnalyticsService(db)
    return [service.summarize(p, with_quotes=quotes) for p in portfolios]


@router.post("", response_model=PortfolioResponse, status_code=201)
def create_portfolio(
    payload: PortfolioCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.broker not in BROKERS:
        raise HTTPException(status_code=422, detail=f"Unknown broker: {payload.broker}")
    portfolio = Portfolio(
        user_id=user.id,
        name=payload.name.strip(),
        broker=payload.broker,
        base_currency=payload.base_currency.upper(),
        benchmark=payload.benchmark,
    )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return _to_response(portfolio)


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
def get_portfolio(
    portfolio_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _to_response(_get_portfolio(db, user, portfolio_id))


@router.put("/{portfolio_id}", response_model=PortfolioResponse)
def update_portfolio(
    portfolio_id: int,
    payload: PortfolioUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolio = _get_portfolio(db, user, portfolio_id)
    if payload.name is not None:
        portfolio.name = payload.name.strip()
    if payload.broker is not None:
        if payload.broker not in BROKERS:
            raise HTTPException(status_code=422, detail=f"Unknown broker: {payload.broker}")
        portfolio.broker = payload.broker
    if payload.base_currency is not None:
        portfolio.base_currency = payload.base_currency.upper()
    if payload.benchmark is not None:
        portfolio.benchmark = payload.benchmark
    db.commit()
    db.refresh(portfolio)
    return _to_response(portfolio)


@router.delete("/{portfolio_id}", status_code=204)
def delete_portfolio(
    portfolio_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolio = _get_portfolio(db, user, portfolio_id)
    db.delete(portfolio)
    db.commit()


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


@router.get("/{portfolio_id}/transactions", response_model=list[TransactionResponse])
def list_transactions(
    portfolio_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolio = _get_portfolio(db, user, portfolio_id)
    txns = (
        db.query(Transaction)
        .filter(Transaction.portfolio_id == portfolio.id)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .all()
    )
    return [TransactionResponse.model_validate(t) for t in txns]


@router.post(
    "/{portfolio_id}/transactions", response_model=TransactionResponse, status_code=201
)
def add_transaction(
    portfolio_id: int,
    payload: TransactionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolio = _get_portfolio(db, user, portfolio_id)
    if payload.type not in TRANSACTION_TYPES:
        raise HTTPException(status_code=422, detail=f"Unknown type: {payload.type}")
    txn = Transaction(portfolio_id=portfolio.id, **payload.model_dump())
    if txn.ticker:
        txn.ticker = txn.ticker.upper()
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return TransactionResponse.model_validate(txn)


@router.delete("/{portfolio_id}/transactions/{txn_id}", status_code=204)
def delete_transaction(
    portfolio_id: int,
    txn_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolio = _get_portfolio(db, user, portfolio_id)
    deleted = (
        db.query(Transaction)
        .filter(Transaction.id == txn_id, Transaction.portfolio_id == portfolio.id)
        .delete()
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.commit()


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


@router.post("/{portfolio_id}/import/preview", response_model=ImportPreviewResponse)
async def import_preview(
    portfolio_id: int,
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolio = _get_portfolio(db, user, portfolio_id)
    content = await file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (limit {MAX_IMPORT_BYTES // 1_000_000} MB).",
        )
    return ImportService(db).preview(portfolio, content, file.filename or "upload.csv")


@router.post("/{portfolio_id}/import/commit", response_model=ImportCommitResponse)
def import_commit(
    portfolio_id: int,
    payload: ImportCommitRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolio = _get_portfolio(db, user, portfolio_id)
    return ImportService(db).commit(portfolio, payload)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


@router.get("/{portfolio_id}/analytics", response_model=PortfolioAnalyticsResponse)
def portfolio_analytics(
    portfolio_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolio = _get_portfolio(db, user, portfolio_id)
    return PortfolioAnalyticsService(db).analyze(portfolio)


@router.get("/{portfolio_id}/insider", response_model=PortfolioInsiderResponse)
def portfolio_insider(
    portfolio_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Insider-trading read on every open position, with portfolio-level advice."""
    from app.services.insider import get_insider_intel
    from app.services.positions import compute_positions

    portfolio = _get_portfolio(db, user, portfolio_id)
    positions, _ = compute_positions(portfolio.transactions)
    open_positions = sorted(
        (p for p in positions.values() if p.is_open),
        key=lambda p: p.cost_basis,
        reverse=True,
    )

    holdings: list[HoldingInsider] = []
    advice: list[str] = []
    no_data: list[str] = []
    for pos in open_positions:
        signal, _trades = get_insider_intel(db, pos.ticker)
        if signal.label == "No activity" and signal.buy_count == signal.sell_count == 0:
            no_data.append(pos.ticker)
        holdings.append(
            HoldingInsider(ticker=pos.ticker, name=pos.name, signal=signal)
        )
        if signal.label == "Bullish":
            advice.append(
                f"{pos.ticker}: insiders are accumulating — "
                + (signal.signals[0] if signal.signals else signal.summary)
                + " Consider this a vote of confidence in your position."
            )
        elif signal.label == "Bearish":
            advice.append(
                f"{pos.ticker}: {signal.summary} Broad insider distribution is worth "
                "monitoring — review your thesis and consider tightening stops."
            )

    if not advice:
        advice.append(
            "No strong insider signals across your holdings right now — "
            "no cluster buying or broad distribution detected."
        )
    if no_data:
        advice.append(
            f"No insider filings available for {', '.join(no_data)} — insider "
            "disclosure coverage is limited outside US-listed securities."
        )

    return PortfolioInsiderResponse(
        portfolio_id=portfolio.id,
        as_of=utcnow(),
        holdings=holdings,
        advice=advice,
        no_data_tickers=no_data,
    )
