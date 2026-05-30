from sqlalchemy.orm import Session

from app.models.holding import Holding
from app.schemas.portfolio import (
    HoldingInsight,
    PortfolioInsightsResponse,
    SectorAllocation,
)
from app.services.stock_analysis import StockAnalysisService


class PortfolioService:
    def __init__(self, db: Session):
        self.db = db
        self.stock_service = StockAnalysisService(db)

    def get_insights(self) -> PortfolioInsightsResponse:
        holdings = self.db.query(Holding).order_by(Holding.ticker).all()
        if not holdings:
            return PortfolioInsightsResponse(
                holdings=[],
                total_cost_basis=0,
                total_market_value=0,
                total_unrealized_pnl=0,
                total_unrealized_pnl_pct=0,
                sector_allocation=[],
                risk_flags=[],
            )

        insights: list[HoldingInsight] = []
        sector_values: dict[str, float] = {}
        total_cost = 0.0
        total_market = 0.0
        stale = False
        overbought_count = 0
        trend_labels: dict[str, int] = {"Bullish": 0, "Neutral": 0, "Bearish": 0}

        for holding in holdings:
            cost_basis = holding.shares * holding.avg_cost
            total_cost += cost_basis

            try:
                analysis = self.stock_service.analyze(holding.ticker)
                stale = stale or analysis.stale
                current_price = analysis.price
                market_value = (
                    holding.shares * current_price if current_price is not None else None
                )
                if market_value is not None:
                    total_market += market_value
                    sector = analysis.sector or "Unknown"
                    sector_values[sector] = sector_values.get(sector, 0) + market_value

                unrealized = (
                    market_value - cost_basis if market_value is not None else None
                )
                unrealized_pct = (
                    (unrealized / cost_basis * 100)
                    if unrealized is not None and cost_basis
                    else None
                )

                trend_labels[analysis.trend.label] = (
                    trend_labels.get(analysis.trend.label, 0) + 1
                )
                if analysis.rsi is not None and analysis.rsi > 70:
                    overbought_count += 1

                insights.append(
                    HoldingInsight(
                        ticker=holding.ticker,
                        shares=holding.shares,
                        avg_cost=holding.avg_cost,
                        current_price=current_price,
                        market_value=market_value,
                        cost_basis=cost_basis,
                        unrealized_pnl=unrealized,
                        unrealized_pnl_pct=round(unrealized_pct, 2)
                        if unrealized_pct is not None
                        else None,
                        sector=analysis.sector,
                        trend_label=analysis.trend.label,
                        sentiment_label=analysis.sentiment.label,
                    )
                )
            except Exception:
                insights.append(
                    HoldingInsight(
                        ticker=holding.ticker,
                        shares=holding.shares,
                        avg_cost=holding.avg_cost,
                        current_price=None,
                        market_value=None,
                        cost_basis=cost_basis,
                        unrealized_pnl=None,
                        unrealized_pnl_pct=None,
                        sector=None,
                        trend_label="Unknown",
                        sentiment_label="Unknown",
                    )
                )

        sector_allocation = []
        if total_market > 0:
            for sector, value in sorted(
                sector_values.items(), key=lambda x: x[1], reverse=True
            ):
                sector_allocation.append(
                    SectorAllocation(
                        sector=sector,
                        weight_pct=round(value / total_market * 100, 2),
                        value=round(value, 2),
                    )
                )

        risk_flags: list[str] = []
        for alloc in sector_allocation:
            if alloc.weight_pct > 40:
                risk_flags.append(
                    f"High concentration in {alloc.sector} ({alloc.weight_pct:.1f}%)"
                )
        if overbought_count >= 2:
            risk_flags.append(
                f"{overbought_count} holdings have RSI above 70 (overbought)"
            )
        if trend_labels.get("Bearish", 0) > len(holdings) / 2:
            risk_flags.append("Majority of holdings show bearish technical trends")

        total_pnl = total_market - total_cost if total_market else None
        total_pnl_pct = (
            (total_pnl / total_cost * 100) if total_pnl is not None and total_cost else None
        )

        return PortfolioInsightsResponse(
            holdings=insights,
            total_cost_basis=round(total_cost, 2),
            total_market_value=round(total_market, 2) if total_market else None,
            total_unrealized_pnl=round(total_pnl, 2) if total_pnl is not None else None,
            total_unrealized_pnl_pct=round(total_pnl_pct, 2)
            if total_pnl_pct is not None
            else None,
            sector_allocation=sector_allocation,
            risk_flags=risk_flags,
            stale=stale,
        )
