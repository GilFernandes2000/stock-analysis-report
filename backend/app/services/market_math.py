"""Currency / FX / price-series helpers shared by the analytics and quote services.

These used to live as private helpers inside ``portfolio_analytics`` and were
being imported across module boundaries (``quotes`` reached in for the
underscore-prefixed names). They are pure functions with no DB or network
dependency, so they belong in their own module.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

# Exchange suffix -> instrument currency fallback (used when Yahoo doesn't
# report a quote currency for a listing).
SUFFIX_CURRENCY: dict[str, str] = {
    ".L": "GBp",
    ".DE": "EUR", ".AS": "EUR", ".PA": "EUR", ".MI": "EUR", ".MC": "EUR",
    ".BR": "EUR", ".VI": "EUR", ".HE": "EUR", ".IR": "EUR", ".LS": "EUR",
    ".F": "EUR", ".BE": "EUR",
    ".SW": "CHF", ".CO": "DKK", ".ST": "SEK", ".OL": "NOK",
    ".TO": "CAD", ".AX": "AUD",
}

# Currencies quoted in a minor unit (pence, agorot, cents) at 1/100 of the major.
_MINOR_UNIT_CURRENCIES = ("GBp", "GBX", "ILA", "ZAc")
_MINOR_TO_MAJOR = {"GBp": "GBP", "GBX": "GBP", "ILA": "ILS", "ZAc": "ZAR"}


def suffix_currency(ticker: str) -> str:
    """Best-guess quote currency from a Yahoo ticker's exchange suffix."""
    upper = ticker.upper()
    for suffix, currency in SUFFIX_CURRENCY.items():
        if upper.endswith(suffix):
            return currency
    return "USD"


def minor_divisor(currency: str | None) -> float:
    """100 for minor-unit currencies (GBp etc.), else 1."""
    return 100.0 if currency in _MINOR_UNIT_CURRENCIES else 1.0


def major_currency(currency: str | None) -> str:
    """Normalize a minor-unit currency code to its major (GBp -> GBP)."""
    if not currency:
        return "USD"
    return _MINOR_TO_MAJOR.get(currency, currency.upper())


def fx_pairs(currencies: Iterable[str | None], base: str) -> list[str]:
    """Yahoo FX symbols (e.g. ``EURUSD=X``) needed to convert into ``base``."""
    pairs = []
    for currency in set(currencies):
        major = major_currency(currency)
        if major and major != base:
            pairs.append(f"{major}{base}=X")
    return pairs


def extract_closes(
    data: "pd.DataFrame | None", symbols: list[str]
) -> dict[str, pd.Series]:
    """Pull a tz-naive, date-normalized Close series per symbol from a
    ``yfinance.download`` result (single- or multi-symbol shape)."""
    closes: dict[str, pd.Series] = {}
    if data is None or data.empty:
        return closes
    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"] if "Close" in data.columns.get_level_values(0) else None
        if close is None:
            return closes
        for symbol in symbols:
            if symbol in close.columns:
                series = close[symbol]
                series.index = pd.to_datetime(series.index).tz_localize(None).normalize()
                closes[symbol] = series
    else:
        # single symbol download
        if "Close" in data.columns and symbols:
            series = data["Close"]
            series.index = pd.to_datetime(series.index).tz_localize(None).normalize()
            closes[symbols[0]] = series
    return closes
