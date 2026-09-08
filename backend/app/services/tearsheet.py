"""Portfolio tearsheet generation — institutional-style report content.

Produces a JSON document (rendered by the frontend report viewer) plus a
markdown fallback, persisted in the reports table.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.models.portfolio import Portfolio
from app.models.report import Report
from app.schemas.portfolio import PortfolioAnalyticsResponse
from app.services.portfolio_analytics import PortfolioAnalyticsService
from app.services.stock_analysis import StockAnalysisService
from app.utils.time import utcnow

logger = logging.getLogger(__name__)

MAX_COMMENTED_HOLDINGS = 10


def _money(value: float | None, currency: str) -> str:
    if value is None:
        return "n/a"
    symbol = {"EUR": "€", "USD": "$", "GBP": "£"}.get(currency, f"{currency} ")
    sign = "-" if value < 0 else ""
    return f"{sign}{symbol}{abs(value):,.2f}"


def _pct(value: float | None, signed: bool = True) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2f}%" if signed else f"{value:.2f}%"


def _vol_quality(vol: float | None) -> str:
    if vol is None:
        return "unknown"
    if vol < 12:
        return "low"
    if vol < 20:
        return "moderate"
    if vol < 30:
        return "elevated"
    return "high"


class TearsheetBuilder:
    def __init__(self, db: Session):
        self.db = db
        self.analytics = PortfolioAnalyticsService(db)
        self.stocks = StockAnalysisService(db)

    def build(self, user_id: int, portfolios: list[Portfolio]) -> Report:
        sections = []
        for portfolio in portfolios:
            analytics = self.analytics.analyze(portfolio)
            enrichment = self._enrich_holdings(analytics)
            commentary = self._commentary(analytics, enrichment)
            sections.append(
                {
                    "portfolio": json.loads(analytics.model_dump_json()),
                    "holdings_analysis": enrichment,
                    "commentary": commentary,
                }
            )

        combined = self._combined_summary(sections) if len(sections) > 1 else None
        names = ", ".join(p.name for p in portfolios)
        title = f"Portfolio Tearsheet — {names}"
        content = {
            "kind": "portfolio",
            "title": title,
            "generated_at": utcnow().isoformat(),
            "portfolio_count": len(sections),
            "combined": combined,
            "sections": sections,
        }
        report = Report(
            kind="portfolio",
            report_type="tearsheet",
            title=title,
            user_id=user_id,
            portfolio_ids=json.dumps([p.id for p in portfolios]),
            content_json=json.dumps(content),
            content_markdown=self._markdown(content),
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    # ------------------------------------------------------------------
    # Per-holding research enrichment (trend / sentiment / analyst view)
    # ------------------------------------------------------------------

    def _enrich_holdings(self, analytics: PortfolioAnalyticsResponse) -> list[dict]:
        ranked = sorted(
            analytics.positions,
            key=lambda p: p.market_value or 0.0,
            reverse=True,
        )[:MAX_COMMENTED_HOLDINGS]
        enriched = []
        for position in ranked:
            entry: dict = {"ticker": position.ticker}
            try:
                analysis = self.stocks.analyze(
                    position.ticker, display_currency=analytics.base_currency
                )
                entry.update(
                    {
                        "trend_label": analysis.trend.label,
                        "trend_score": analysis.trend.score,
                        "sentiment_label": analysis.sentiment.label,
                        "rsi": analysis.rsi,
                        "analyst_upside_pct": analysis.analyst_upside_pct,
                        "recommendation": getattr(analysis, "recommendation", None),
                        "pe": analysis.pe,
                        "dividend": analysis.dividend,
                        "insider_label": analysis.insider_signal.label
                        if analysis.insider_signal
                        else None,
                        "insider_summary": analysis.insider_signal.summary
                        if analysis.insider_signal
                        else None,
                        "insider_signals": analysis.insider_signal.signals
                        if analysis.insider_signal
                        else [],
                    }
                )
            except Exception as exc:
                logger.debug("Enrichment failed for %s: %s", position.ticker, exc)
                entry["error"] = "research data unavailable"
            enriched.append(entry)
        return enriched

    # ------------------------------------------------------------------
    # Narrative
    # ------------------------------------------------------------------

    def _commentary(
        self, a: PortfolioAnalyticsResponse, enrichment: list[dict]
    ) -> dict:
        ccy = a.base_currency
        research = {e["ticker"]: e for e in enrichment}

        # Executive summary
        parts = [
            f"As of {a.as_of.strftime('%B %d, %Y')}, {a.name} holds "
            f"{len(a.positions)} open positions with a market value of "
            f"{_money(a.market_value, ccy)}"
        ]
        if a.cash_balance > 0:
            parts.append(f" plus {_money(a.cash_balance, ccy)} in cash")
        parts.append(
            f". Since inception the portfolio has generated a total return of "
            f"{_money(a.total_return, ccy)}"
        )
        if a.total_return_pct is not None:
            parts.append(f" ({_pct(a.total_return_pct)} on invested capital)")
        parts.append(
            f", comprising {_money(a.unrealized_pnl, ccy)} unrealized, "
            f"{_money(a.realized_pnl, ccy)} realized and "
            f"{_money(a.dividends_received, ccy)} of dividend income, "
            f"net of {_money(a.fees_paid, ccy)} in fees."
        )
        if a.risk.twr_pct is not None and a.risk.benchmark_return_pct is not None:
            diff = a.risk.twr_pct - a.risk.benchmark_return_pct
            verb = "outperforming" if diff >= 0 else "underperforming"
            parts.append(
                f" On a time-weighted basis the portfolio returned "
                f"{_pct(a.risk.twr_pct)}, {verb} its benchmark ({a.benchmark}, "
                f"{_pct(a.risk.benchmark_return_pct)}) by {abs(diff):.1f} percentage points."
            )
        executive = "".join(parts)

        # Performance
        perf_parts = []
        if a.day_change_pct is not None:
            perf_parts.append(
                f"The portfolio moved {_pct(a.day_change_pct)} "
                f"({_money(a.day_change, ccy)}) in the latest session."
            )
        if a.risk.best_day_pct is not None and a.risk.worst_day_pct is not None:
            perf_parts.append(
                f"Over the holding period the best single day added "
                f"{_pct(a.risk.best_day_pct)} while the worst day cost "
                f"{_pct(a.risk.worst_day_pct)}."
            )
        if a.risk.max_drawdown_pct is not None:
            perf_parts.append(
                f"The maximum peak-to-trough drawdown was {_pct(a.risk.max_drawdown_pct)}."
            )
        if a.top_contributors:
            best = a.top_contributors[0]
            perf_parts.append(
                f"{best.ticker} is the largest contributor with "
                f"{_money(best.total_pnl, ccy)} of total P&L."
            )
        if a.top_detractors:
            worst = a.top_detractors[0]
            perf_parts.append(
                f"{worst.ticker} is the largest detractor at "
                f"{_money(worst.total_pnl, ccy)}."
            )
        performance = " ".join(perf_parts) or "Insufficient history for performance attribution."

        # Risk
        risk_parts = []
        if a.risk.volatility_pct is not None:
            risk_parts.append(
                f"Annualized volatility stands at {_pct(a.risk.volatility_pct, signed=False)} "
                f"({_vol_quality(a.risk.volatility_pct)})."
            )
        if a.risk.sharpe is not None:
            quality = (
                "strong" if a.risk.sharpe > 1 else "adequate" if a.risk.sharpe > 0.5 else "weak"
            )
            risk_parts.append(
                f"The Sharpe ratio of {a.risk.sharpe:.2f} indicates {quality} "
                "risk-adjusted returns."
            )
        if a.risk.beta is not None:
            stance = (
                "more volatile than" if a.risk.beta > 1.1
                else "less volatile than" if a.risk.beta < 0.9
                else "in line with"
            )
            risk_parts.append(
                f"A beta of {a.risk.beta:.2f} versus {a.benchmark} means the portfolio "
                f"trades {stance} the broad market."
            )
        risk = " ".join(risk_parts) or "Insufficient history for risk statistics."

        # Allocation
        alloc_parts = []
        if a.sector_allocation:
            top = a.sector_allocation[0]
            alloc_parts.append(
                f"{top.label} is the largest sector exposure at "
                f"{_pct(top.weight_pct, signed=False)} of assets"
            )
            if len(a.sector_allocation) > 1:
                second = a.sector_allocation[1]
                alloc_parts.append(
                    f", followed by {second.label} at {_pct(second.weight_pct, signed=False)}"
                )
            alloc_parts.append(".")
        if a.currency_allocation and len(a.currency_allocation) > 1:
            top_ccy = a.currency_allocation[0]
            alloc_parts.append(
                f" By currency, {_pct(top_ccy.weight_pct, signed=False)} of the book "
                f"is denominated in {top_ccy.label}."
            )
        allocation = "".join(alloc_parts) or "No allocation data available."

        # Holdings commentary
        holdings = []
        for position in sorted(
            a.positions, key=lambda p: p.market_value or 0.0, reverse=True
        )[:MAX_COMMENTED_HOLDINGS]:
            r = research.get(position.ticker, {})
            text_parts = [
                f"{position.shares:g} shares at an average cost of "
                f"{_money(position.avg_cost, ccy)}"
            ]
            if position.current_price is not None:
                text_parts.append(
                    f"; last price {_money(position.current_price, ccy)} for an "
                    f"unrealized P&L of {_money(position.unrealized_pnl, ccy)} "
                    f"({_pct(position.unrealized_pnl_pct)})"
                )
            text_parts.append(".")
            if position.dividends:
                text_parts.append(
                    f" Dividend income to date: {_money(position.dividends, ccy)}."
                )
            if position.realized_pnl:
                text_parts.append(
                    f" Realized P&L from partial sales: {_money(position.realized_pnl, ccy)}."
                )
            signals = []
            if r.get("trend_label"):
                signals.append(f"technical trend {r['trend_label'].lower()}")
            if r.get("sentiment_label"):
                signals.append(f"news sentiment {r['sentiment_label'].lower()}")
            if r.get("analyst_upside_pct") is not None:
                signals.append(
                    f"analyst targets imply {_pct(r['analyst_upside_pct'])} upside"
                )
            if r.get("insider_label") in ("Bullish", "Bearish"):
                signals.append(f"insider activity {r['insider_label'].lower()}")
            if signals:
                text_parts.append(f" Research view: {', '.join(signals)}.")
            if r.get("insider_label") in ("Bullish", "Bearish") and r.get("insider_summary"):
                text_parts.append(f" {r['insider_summary']}")
            holdings.append(
                {
                    "ticker": position.ticker,
                    "name": position.name,
                    "weight_pct": position.weight_pct,
                    "text": "".join(text_parts),
                }
            )

        # Outlook / action items
        outlook: list[str] = list(a.risk_flags)
        for e in enrichment:
            if e.get("insider_label") == "Bullish":
                detail = (e.get("insider_signals") or [e.get("insider_summary", "")])[0]
                outlook.append(
                    f"Insider buying at {e['ticker']}: {detail} A supportive signal "
                    "for holding or adding."
                )
            elif e.get("insider_label") == "Bearish":
                outlook.append(
                    f"Insider selling at {e['ticker']}: {e.get('insider_summary', '')} "
                    "Review the position and consider tightening risk."
                )
        overbought = [
            e["ticker"]
            for e in enrichment
            if isinstance(e.get("rsi"), (int, float)) and e["rsi"] > 70
        ]
        if overbought:
            outlook.append(
                f"RSI above 70 on {', '.join(overbought)} — consider taking profits "
                "or tightening stops."
            )
        oversold = [
            e["ticker"]
            for e in enrichment
            if isinstance(e.get("rsi"), (int, float)) and e["rsi"] < 30
        ]
        if oversold:
            outlook.append(
                f"RSI below 30 on {', '.join(oversold)} — oversold territory may "
                "offer accumulation opportunities."
            )
        if a.cash_balance > 0 and a.market_value and a.cash_balance > 0.15 * a.market_value:
            outlook.append(
                f"Cash of {_money(a.cash_balance, ccy)} exceeds 15% of assets — "
                "consider deployment or confirm it is intentional dry powder."
            )
        if not outlook:
            outlook.append("No structural risk flags detected; maintain current course.")

        return {
            "executive_summary": executive,
            "performance": performance,
            "risk": risk,
            "allocation": allocation,
            "holdings": holdings,
            "outlook": outlook,
        }

    # ------------------------------------------------------------------

    @staticmethod
    def _combined_summary(sections: list[dict]) -> dict:
        total_value = sum(s["portfolio"]["market_value"] or 0 for s in sections)
        total_return = sum(s["portfolio"]["total_return"] or 0 for s in sections)
        total_dividends = sum(s["portfolio"]["dividends_received"] or 0 for s in sections)
        total_fees = sum(s["portfolio"]["fees_paid"] or 0 for s in sections)
        currencies = {s["portfolio"]["base_currency"] for s in sections}
        return {
            "portfolio_names": [s["portfolio"]["name"] for s in sections],
            "market_value": round(total_value, 2),
            "total_return": round(total_return, 2),
            "dividends_received": round(total_dividends, 2),
            "fees_paid": round(total_fees, 2),
            "mixed_currencies": len(currencies) > 1,
            "base_currency": sections[0]["portfolio"]["base_currency"],
        }

    @staticmethod
    def _markdown(content: dict) -> str:
        lines = [f"# {content['title']}", "", f"Generated: {content['generated_at']}", ""]
        for section in content["sections"]:
            p = section["portfolio"]
            c = section["commentary"]
            lines += [
                f"## {p['name']}",
                "",
                c["executive_summary"],
                "",
                "### Performance",
                c["performance"],
                "",
                "### Risk",
                c["risk"],
                "",
                "### Allocation",
                c["allocation"],
                "",
                "### Holdings",
            ]
            for holding in c["holdings"]:
                lines.append(f"- **{holding['ticker']}** — {holding['text']}")
            lines += ["", "### Outlook"]
            for item in c["outlook"]:
                lines.append(f"- {item}")
            lines.append("")
        return "\n".join(lines)
