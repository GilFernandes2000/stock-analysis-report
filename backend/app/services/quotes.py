"""Fast, batched quotes for a list of tickers (watchlist / favorites).

One yfinance download covers every ticker plus the FX pairs needed to convert
into the user's display currency; profile data (name, sector, market cap,
quote currency) comes from the shared 7-day profile cache. Deep per-stock
analysis (trend, sentiment, insider) is intentionally left to the detail page.
"""

from __future__ import annotations

import logging

import yfinance as yf
from sqlalchemy.orm import Session

from app.schemas.favorite import Quote
from app.services.currency_service import CurrencyService
from app.services.market_math import (
    extract_closes,
    fx_pairs,
    major_currency,
    minor_divisor,
    suffix_currency,
)
from app.services.portfolio_analytics import TickerProfileCache

logger = logging.getLogger(__name__)


class QuoteService:
    def __init__(self, db: Session):
        self.db = db
        self.profiles = TickerProfileCache(db)
        self.currency = CurrencyService(db)

    def get_quotes(self, tickers: list[str], display_currency: str) -> tuple[list[Quote], bool]:
        tickers = [t.upper().strip() for t in dict.fromkeys(tickers) if t.strip()]
        if not tickers:
            return [], False

        profiles = self.profiles.get_many(tickers)
        currencies = {
            t: (profiles.get(t, {}).get("currency") or suffix_currency(t)) for t in tickers
        }

        pairs = fx_pairs(currencies.values(), display_currency)
        symbols = list(dict.fromkeys(tickers + pairs))

        closes: dict = {}
        stale = False
        try:
            data = yf.download(
                symbols, period="7d", interval="1d", progress=False,
                auto_adjust=False, group_by="column", threads=True,
            )
            closes = extract_closes(data, symbols)
        except Exception as exc:
            logger.warning("Quote download failed: %s", exc)
            stale = True

        quotes: list[Quote] = []
        for ticker in tickers:
            profile = profiles.get(ticker, {})
            native_ccy = currencies[ticker]
            native_price = None
            change_pct = None
            series = closes.get(ticker)
            if series is not None and not series.dropna().empty:
                clean = series.dropna()
                divisor = minor_divisor(native_ccy)
                native_price = float(clean.iloc[-1]) / divisor
                if len(clean) >= 2 and float(clean.iloc[-2]):
                    change_pct = (float(clean.iloc[-1]) / float(clean.iloc[-2]) - 1) * 100
            else:
                stale = True

            display_price = None
            if native_price is not None:
                rate = self._fx_last(closes, native_ccy, display_currency)
                display_price = round(native_price * rate, 4)

            market_cap = profile.get("market_cap")
            quotes.append(
                Quote(
                    ticker=ticker,
                    name=profile.get("name"),
                    sector=profile.get("sector"),
                    country=profile.get("country"),
                    native_currency=major_currency(native_ccy),
                    native_price=round(native_price, 4) if native_price is not None else None,
                    display_currency=display_currency,
                    price=display_price,
                    change_pct=round(change_pct, 2) if change_pct is not None else None,
                    market_cap=float(market_cap) if market_cap else None,
                    pe=profile.get("pe"),
                )
            )
        return quotes, stale

    def _fx_last(self, closes: dict, native_ccy: str | None, base: str) -> float:
        major = major_currency(native_ccy)
        if major == base:
            return 1.0
        series = closes.get(f"{major}{base}=X")
        if series is not None and not series.dropna().empty:
            return float(series.dropna().iloc[-1])
        return 1.0
