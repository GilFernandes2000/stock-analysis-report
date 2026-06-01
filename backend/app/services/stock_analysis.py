from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.schemas.stock import (
    AnalystTarget,
    InsiderTrade,
    NewsItem,
    SentimentSummary,
    StockAnalysisResponse,
    TrendAnalysis,
)
from app.services.currency_service import (
    CurrencyService,
    NormalizedMoney,
    currency_note,
    normalize_to_major,
)
from app.services.finviz_client import FinvizService
from app.services.ticker_symbols import (
    is_likely_european,
    is_valid_ticker,
    normalize_ticker,
    resolve_ticker_candidates,
)
from app.services.yahoo_client import YahooFinanceClient


class StockAnalysisService:
    def __init__(self, db: Session):
        self.db = db
        self.finviz = FinvizService(db)
        self.yahoo = YahooFinanceClient()
        self.currency = CurrencyService(db)

    def analyze(
        self, ticker: str, display_currency: str | None = None
    ) -> StockAnalysisResponse:
        if not is_valid_ticker(ticker):
            raise ValueError(f"Invalid ticker format: {ticker}")

        display = self.currency.validate_display_currency(
            display_currency or settings.default_display_currency
        )

        candidates = resolve_ticker_candidates(ticker)
        errors: list[str] = []

        if is_likely_european(candidates[0]):
            for symbol in candidates:
                try:
                    return self._analyze_yahoo(symbol, requested=ticker, display_currency=display)
                except Exception as exc:
                    errors.append(f"{symbol} (Yahoo): {exc}")

        for symbol in candidates:
            try:
                return self._analyze_finviz(symbol, requested=ticker, display_currency=display)
            except Exception as exc:
                errors.append(f"{symbol} (Finviz): {exc}")

        for symbol in candidates:
            try:
                return self._analyze_yahoo(symbol, requested=ticker, display_currency=display)
            except Exception as exc:
                errors.append(f"{symbol} (Yahoo): {exc}")

        raise ValueError(
            "Could not find stock data. For European listings use exchange suffixes "
            "e.g. SAP.DE, ASML.AS, VOD.L, MC.PA, NESN.SW. Details: "
            + "; ".join(errors[:3])
        )

    def _money_fields(
        self,
        price: float | None,
        raw_currency: str | None,
        display_currency: str,
        *,
        finviz_default: bool = False,
    ) -> dict[str, Any]:
        if price is None:
            return {
                "native_currency": None,
                "native_price": None,
                "display_currency": display_currency,
                "display_price": None,
                "currency_note": None,
                "price": None,
                "currency": display_currency,
            }

        raw = "USD" if finviz_default and not raw_currency else raw_currency
        normalized = normalize_to_major(price, raw)
        display_price = self.currency.convert(
            normalized.amount, normalized.currency, display_currency
        )
        note = currency_note(normalized)
        return {
            "native_currency": normalized.currency,
            "native_price": normalized.amount,
            "display_currency": display_currency,
            "display_price": display_price,
            "currency_note": note,
            "price": display_price,
            "currency": display_currency,
        }

    def _convert_target(
        self,
        target: float | None,
        native_currency: str | None,
        display_currency: str,
    ) -> tuple[float | None, float | None]:
        if target is None:
            return None, None
        native = float(target)
        if native_currency:
            display = self.currency.convert(native, native_currency, display_currency)
        else:
            display = native
        return display, native

    def _analyze_finviz(
        self, ticker: str, *, requested: str, display_currency: str
    ) -> StockAnalysisResponse:
        from app.services.sentiment import analyze_headlines

        ticker = normalize_ticker(ticker)
        stale = False

        stock, stock_stale = self.finviz.get_stock_raw(ticker)
        stale = stale or stock_stale

        news_raw, news_stale = self.finviz.get_news(ticker)
        stale = stale or news_stale

        targets_raw, targets_stale = self.finviz.get_analyst_targets(ticker)
        stale = stale or targets_stale

        insider_raw, insider_stale = self.finviz.get_insider(ticker)
        stale = stale or insider_stale

        numeric = self.finviz.extract_numeric_fields(stock)
        from app.services.analysis import compute_technical_trend

        trend_data = compute_technical_trend(numeric)

        headlines = [item[1] for item in news_raw if len(item) > 1]
        sentiment_data = analyze_headlines(headlines)

        news_items = []
        for item in news_raw[:10]:
            title = item[1] if len(item) > 1 else str(item)
            url = item[2] if len(item) > 2 else None
            date = item[0] if len(item) > 0 else None
            matched = next(
                (s for s in sentiment_data["items"] if s["title"] == title), None
            )
            news_items.append(
                NewsItem(
                    title=title,
                    url=url,
                    date=date,
                    sentiment=matched["sentiment"] if matched else None,
                    compound_score=matched["compound_score"] if matched else None,
                )
            )

        money = self._money_fields(
            numeric.get("price"), None, display_currency, finviz_default=True
        )
        native_currency = money["native_currency"] or "USD"

        analyst_targets = []
        for t in targets_raw[:10]:
            raw_target = t.get("target_to") or t.get("target_from")
            native_target = float(raw_target) if raw_target else None
            display_target, native_pt = self._convert_target(
                native_target, native_currency, display_currency
            )
            analyst_targets.append(
                AnalystTarget(
                    analyst=t.get("analyst"),
                    price_target=display_target,
                    native_price_target=native_pt,
                    date=t.get("date"),
                )
            )

        median_target = self.finviz.median_analyst_target(targets_raw)
        _, native_median = self._convert_target(
            median_target, native_currency, display_currency
        )
        upside = self.finviz.analyst_upside_pct(
            money["native_price"], native_median
        )

        insider_trades = [
            InsiderTrade(
                insider=t.get("Insider Trading"),
                relationship=t.get("Relationship"),
                transaction=t.get("Transaction"),
                shares=t.get("#Shares"),
                value=t.get("Value ($)"),
                date=t.get("Date"),
            )
            for t in insider_raw[:10]
        ]

        return StockAnalysisResponse(
            ticker=normalize_ticker(requested),
            company=stock.get("Company"),
            sector=stock.get("Sector"),
            industry=stock.get("Industry"),
            country=stock.get("Country"),
            data_source="finviz",
            **money,
            change=stock.get("Change"),
            market_cap=stock.get("Market Cap"),
            pe=stock.get("P/E"),
            eps=stock.get("EPS (ttm)"),
            dividend=stock.get("Dividend"),
            beta=stock.get("Beta"),
            rsi=numeric.get("rsi"),
            sma20=numeric.get("sma20"),
            sma50=numeric.get("sma50"),
            sma200=numeric.get("sma200"),
            inst_own=stock.get("Inst Own"),
            insider_own=stock.get("Insider Own"),
            short_float=stock.get("Short Float"),
            perf_week=stock.get("Perf Week"),
            perf_month=stock.get("Perf Month"),
            perf_quarter=stock.get("Perf Quarter"),
            perf_ytd=stock.get("Perf YTD"),
            high_52w=stock.get("52W High"),
            low_52w=stock.get("52W Low"),
            chart_url=self.finviz.chart_url(ticker),
            trend=TrendAnalysis(**trend_data),
            sentiment=SentimentSummary(
                label=sentiment_data["label"],
                average_compound=sentiment_data["average_compound"],
                positive_count=sentiment_data["positive_count"],
                negative_count=sentiment_data["negative_count"],
                neutral_count=sentiment_data["neutral_count"],
                headlines=news_items,
            ),
            analyst_targets=analyst_targets,
            analyst_upside_pct=upside,
            insider_trades=insider_trades,
            raw=stock,
            stale=stale,
        )

    def _analyze_yahoo(
        self, ticker: str, *, requested: str, display_currency: str
    ) -> StockAnalysisResponse:
        data = self.yahoo.fetch_analysis(ticker)
        numeric = data["numeric"]
        sentiment_data = data["sentiment_data"]
        native_currency = data["currency"]

        money = self._money_fields(
            numeric.get("price"),
            native_currency,
            display_currency,
        )
        if data.get("was_minor_unit") and money["native_price"] is not None:
            money["currency_note"] = currency_note(
                NormalizedMoney(
                    amount=money["native_price"],
                    currency=native_currency or "GBP",
                    raw_currency=data.get("raw_currency"),
                    was_minor_unit=True,
                )
            )

        news_items = []
        for title, url, date in data["news_raw"]:
            matched = next(
                (s for s in sentiment_data["items"] if s["title"] == title), None
            )
            news_items.append(
                NewsItem(
                    title=title,
                    url=url,
                    date=date,
                    sentiment=matched["sentiment"] if matched else None,
                    compound_score=matched["compound_score"] if matched else None,
                )
            )

        analyst_targets = []
        if data["target_mean"]:
            native_target = float(data["target_mean"])
            display_target, native_pt = self._convert_target(
                native_target, native_currency, display_currency
            )
            analyst_targets.append(
                AnalystTarget(
                    analyst="Consensus (Yahoo)",
                    price_target=display_target,
                    native_price_target=native_pt,
                    date=None,
                )
            )

        high = data["high_52w"]
        low = data["low_52w"]
        native_price = money["native_price"]
        display_price = money["display_price"]

        high_display = (
            self.currency.convert(float(high), native_currency, display_currency)
            if high is not None and native_currency
            else None
        )
        low_display = (
            self.currency.convert(float(low), native_currency, display_currency)
            if low is not None and native_currency
            else None
        )

        return StockAnalysisResponse(
            ticker=normalize_ticker(requested),
            company=data["company"],
            sector=data["sector"],
            industry=data["industry"],
            country=data.get("country"),
            exchange=data.get("exchange"),
            **money,
            data_source="yahoo",
            change=data["change"],
            market_cap=data["market_cap"],
            pe=data["pe"],
            eps=data["eps"],
            dividend=data["dividend"],
            beta=data["beta"],
            rsi=numeric.get("rsi"),
            sma20=numeric.get("sma20"),
            sma50=numeric.get("sma50"),
            sma200=numeric.get("sma200"),
            perf_week=f"{numeric['perf_week']:+.2f}%" if numeric.get("perf_week") is not None else None,
            perf_month=f"{numeric['perf_month']:+.2f}%" if numeric.get("perf_month") is not None else None,
            perf_quarter=f"{numeric['perf_quarter']:+.2f}%" if numeric.get("perf_quarter") is not None else None,
            perf_ytd=f"{numeric['perf_ytd']:+.2f}%" if numeric.get("perf_ytd") is not None else None,
            high_52w=(
                f"{high_display:.2f} ({((display_price - high_display) / high_display * 100):+.2f}%)"
                if high_display is not None and display_price is not None
                else str(high) if high else None
            ),
            low_52w=(
                f"{low_display:.2f} ({((display_price - low_display) / low_display * 100):+.2f}%)"
                if low_display is not None and display_price is not None
                else str(low) if low else None
            ),
            chart_url=self.yahoo.chart_url(ticker),
            trend=TrendAnalysis(**data["trend_data"]),
            sentiment=SentimentSummary(
                label=sentiment_data["label"],
                average_compound=sentiment_data["average_compound"],
                positive_count=sentiment_data["positive_count"],
                negative_count=sentiment_data["negative_count"],
                neutral_count=sentiment_data["neutral_count"],
                headlines=news_items,
            ),
            analyst_targets=analyst_targets,
            analyst_upside_pct=data["upside"],
            insider_trades=[],
            raw=data["raw"],
            stale=False,
        )

    def analyze_batch(self, tickers: list[str]) -> dict[str, Any]:
        results = {}
        for ticker in tickers:
            try:
                results[ticker] = self.analyze(ticker).model_dump()
            except Exception as exc:
                results[ticker] = {"error": str(exc)}
        return results
