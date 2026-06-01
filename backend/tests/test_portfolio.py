from unittest.mock import MagicMock, patch

import pytest

from app.models.holding import Holding
from app.services.portfolio import PortfolioService


@pytest.fixture
def mock_db():
    return MagicMock()


def test_portfolio_insights_empty(mock_db):
    mock_db.query.return_value.order_by.return_value.all.return_value = []
    service = PortfolioService(mock_db)
    result = service.get_insights()
    assert result.holdings == []
    assert result.total_cost_basis == 0
    assert result.risk_flags == []


@patch("app.services.portfolio.StockAnalysisService")
def test_portfolio_insights_with_holdings(mock_stock_service, mock_db):
    holding = Holding(id=1, ticker="AAPL", shares=10, avg_cost=150.0, notes=None)
    mock_db.query.return_value.order_by.return_value.all.return_value = [holding]

    analysis = MagicMock()
    analysis.stale = False
    analysis.display_price = 200.0
    analysis.sector = "Technology"
    analysis.trend.label = "Bullish"
    analysis.sentiment.label = "moderately positive"
    analysis.rsi = 55.0

    mock_stock_service.return_value.analyze.return_value = analysis
    service = PortfolioService(mock_db)
    result = service.get_insights(display_currency="EUR")

    assert len(result.holdings) == 1
    assert result.holdings[0].ticker == "AAPL"
    assert result.holdings[0].cost_basis == 1500.0
    assert result.holdings[0].market_value == 2000.0
    assert result.holdings[0].unrealized_pnl == 500.0
    assert result.total_cost_basis == 1500.0
    assert result.total_market_value == 2000.0
    assert result.display_currency == "EUR"
    mock_stock_service.return_value.analyze.assert_called_with(
        "AAPL", display_currency="EUR"
    )
