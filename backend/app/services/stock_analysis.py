from typing import Any

from sqlalchemy.orm import Session

from app.schemas.stock import (
    AnalystTarget,
    InsiderTrade,
    NewsItem,
    SentimentSummary,
    StockAnalysisResponse,
    TrendAnalysis,
)
from app.services.analysis import compute_technical_trend
from app.services.finviz_client import FinvizService
from app.services.sentiment import analyze_headlines


class StockAnalysisService:
    def __init__(self, db: Session):
        self.finviz = FinvizService(db)

    def analyze(self, ticker: str) -> StockAnalysisResponse:
        ticker = ticker.upper().strip()
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

        analyst_targets = [
            AnalystTarget(
                analyst=t.get("analyst"),
                price_target=t.get("target_to") or t.get("target_from"),
                date=t.get("date"),
            )
            for t in targets_raw[:10]
        ]

        median_target = self.finviz.median_analyst_target(targets_raw)
        upside = self.finviz.analyst_upside_pct(numeric.get("price"), median_target)

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
            ticker=ticker,
            company=stock.get("Company"),
            sector=stock.get("Sector"),
            industry=stock.get("Industry"),
            price=numeric.get("price"),
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

    def analyze_batch(self, tickers: list[str]) -> dict[str, Any]:
        results = {}
        for ticker in tickers:
            try:
                results[ticker] = self.analyze(ticker).model_dump()
            except Exception as exc:
                results[ticker] = {"error": str(exc)}
        return results
