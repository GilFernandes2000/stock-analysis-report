from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time import utcnow

# Transaction types
TXN_BUY = "buy"
TXN_SELL = "sell"
TXN_DIVIDEND = "dividend"
TXN_DEPOSIT = "deposit"
TXN_WITHDRAWAL = "withdrawal"
TXN_FEE = "fee"
TXN_INTEREST = "interest"
TXN_TAX = "tax"
TXN_OTHER = "other"

TRANSACTION_TYPES = {
    TXN_BUY,
    TXN_SELL,
    TXN_DIVIDEND,
    TXN_DEPOSIT,
    TXN_WITHDRAWAL,
    TXN_FEE,
    TXN_INTEREST,
    TXN_TAX,
    TXN_OTHER,
}

BROKERS = {"degiro", "trading212", "manual"}


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    broker: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="EUR")
    benchmark: Mapped[str] = mapped_column(String(32), nullable=False, default="^GSPC")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="portfolios")  # noqa: F821
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan"
    )


class Transaction(Base):
    """A single portfolio event imported from a broker or entered manually.

    Money conventions:
    - `amount` is the signed cash impact in the portfolio base currency,
      excluding fees (buy < 0, sell > 0, dividend > 0, deposit > 0, fee < 0).
    - `fees` is always >= 0 and recorded in base currency.
    - `price` is per-share in `currency` (the traded instrument's currency).
    """

    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "external_id", name="uq_txn_external"),
        # Analytics loads a portfolio's transactions ordered by date.
        Index("ix_txn_portfolio_date", "portfolio_id", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ticker: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    isin: Mapped[str | None] = mapped_column(String(16), nullable=True)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    shares: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fees: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fx_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    portfolio: Mapped[Portfolio] = relationship(back_populates="transactions")
