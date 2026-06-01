from __future__ import annotations

from typing import Any

import yfinance as yf

from app.services.analysis import compute_technical_trend
from app.services.currency_service import minor_unit_divisor, normalize_to_major
from app.services.finviz_client import FinvizService
from app.services.sentiment import analyze_headlines
from app.services.technical_indicators import (
    compute_rsi,
    performance_pct,
    price_vs_sma_pct,
    sma,
    ytd_performance_pct,
)
from app.services.ticker_symbols import normalize_ticker


def _format_market_cap(value: float | None) -> str | None:
    if value is None:
        return None
    if value >= 1e12:
        return f"{value / 1e12:.2f}T"
    if value >= 1e9:
        return f"{value / 1e9:.2f}B"
    if value >= 1e6:
        return f"{value / 1e6:.2f}M"
    return str(int(value))


def _format_change(pct: float | None) -> str | None:
    if pct is None:
        return None
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


def _extract_news(ticker: yf.Ticker, company: str | None) -> list[tuple[str, str | None, str | None]]:
    items: list[tuple[str, str | None, str | None]] = []
    company_token = (company or "").split()[0].upper() if company else ""

    for entry in ticker.news or []:
        content = entry.get("content") if isinstance(entry, dict) else None
        if not content:
            continue
        title = content.get("title") or ""
        if not title:
            continue
        # Prefer headlines mentioning the company when Yahoo returns broad feeds
        if company_token and company_token not in title.upper() and ticker.ticker.upper() not in title.upper():
            continue
        url = None
        canonical = content.get("canonicalUrl") or content.get("clickThroughUrl")
        if isinstance(canonical, dict):
            url = canonical.get("url")
        date = content.get("pubDate") or content.get("displayTime")
        items.append((title, url, date))
        if len(items) >= 10:
            break
    return items


class YahooFinanceClient:
    @staticmethod
    def chart_url(symbol: str) -> str:
        return f"https://finance.yahoo.com/quote/{normalize_ticker(symbol)}/chart"

    @staticmethod
    def fetch_analysis(symbol: str) -> dict[str, Any]:
        symbol = normalize_ticker(symbol)
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}

        if not info.get("regularMarketPrice") and not info.get("currentPrice"):
            raise ValueError(f"No market data found for {symbol}")

        hist = ticker.history(period="1y")
        if hist.empty:
            raise ValueError(f"No price history for {symbol}")

        closes = hist["Close"].tolist()
        dates = hist.index.tolist()
        raw_price = float(
            info.get("regularMarketPrice") or info.get("currentPrice") or closes[-1]
        )
        raw_currency = info.get("currency")
        divisor = minor_unit_divisor(raw_currency)
        if divisor != 1:
            closes = [c / divisor for c in closes]
        normalized = normalize_to_major(raw_price, raw_currency)
        price = normalized.amount

        rsi = compute_rsi(closes)
        sma20 = price_vs_sma_pct(price, sma(closes, 20))
        sma50 = price_vs_sma_pct(price, sma(closes, 50))
        sma200 = price_vs_sma_pct(price, sma(closes, 200))

        numeric = {
            "price": price,
            "rsi": rsi,
            "sma20": sma20,
            "sma50": sma50,
            "sma200": sma200,
            "beta": info.get("beta"),
            "perf_week": performance_pct(closes, 5),
            "perf_month": performance_pct(closes, 21),
            "perf_quarter": performance_pct(closes, 63),
            "perf_ytd": ytd_performance_pct(closes, dates),
        }

        trend_data = compute_technical_trend(numeric)

        company = info.get("longName") or info.get("shortName")
        news_raw = _extract_news(ticker, company)
        headlines = [n[0] for n in news_raw]
        sentiment_data = analyze_headlines(headlines)

        target_mean = info.get("targetMeanPrice") or info.get("targetMedianPrice")
        if target_mean is not None and divisor != 1:
            target_mean = float(target_mean) / divisor
        upside = FinvizService.analyst_upside_pct(price, float(target_mean) if target_mean else None)

        dividend = info.get("dividendYield")
        dividend_str = f"{float(dividend) * 100:.2f}%" if dividend else None

        exchange = info.get("exchange") or info.get("fullExchangeName")

        high_52w = info.get("fiftyTwoWeekHigh")
        low_52w = info.get("fiftyTwoWeekLow")
        if divisor != 1:
            if high_52w is not None:
                high_52w = float(high_52w) / divisor
            if low_52w is not None:
                low_52w = float(low_52w) / divisor

        return {
            "symbol": symbol,
            "company": company,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "raw_currency": raw_currency,
            "currency": normalized.currency,
            "exchange": exchange,
            "price": price,
            "was_minor_unit": normalized.was_minor_unit,
            "change": _format_change(info.get("regularMarketChangePercent")),
            "market_cap": _format_market_cap(info.get("marketCap")),
            "pe": str(info.get("trailingPE")) if info.get("trailingPE") else None,
            "eps": str(info.get("trailingEps")) if info.get("trailingEps") else None,
            "dividend": dividend_str,
            "beta": str(info.get("beta")) if info.get("beta") is not None else None,
            "numeric": numeric,
            "trend_data": trend_data,
            "sentiment_data": sentiment_data,
            "news_raw": news_raw,
            "target_mean": target_mean,
            "upside": upside,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "recommendation": info.get("recommendationKey"),
            "raw": info,
        }
