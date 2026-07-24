from datetime import datetime

import pandas as pd
import pytest

from app.models.portfolio import Portfolio, Transaction
from app.models.user import User
from app.services import portfolio_analytics as pa
from app.services.auth import hash_password
from app.services.portfolio_analytics import PortfolioAnalyticsService


@pytest.fixture()
def portfolio(db_session):
    user = User(username="ana", display_name="Ana", password_hash=hash_password("x" * 8))
    db_session.add(user)
    db_session.flush()
    p = Portfolio(user_id=user.id, name="Test", broker="manual", base_currency="EUR", benchmark="^GSPC")
    db_session.add(p)
    db_session.flush()
    db_session.add_all(
        [
            Transaction(
                portfolio_id=p.id, type="deposit", date=datetime(2024, 1, 1), amount=2000.0
            ),
            Transaction(
                portfolio_id=p.id, type="buy", date=datetime(2024, 1, 2),
                ticker="AAPL", shares=10, price=100.0, currency="USD",
                amount=-1000.0, fees=2.0,
            ),
            Transaction(
                portfolio_id=p.id, type="dividend", date=datetime(2024, 1, 8),
                ticker="AAPL", amount=5.0,
            ),
        ]
    )
    db_session.commit()
    return p


@pytest.fixture()
def fake_market(monkeypatch):
    dates = pd.bdate_range("2024-01-02", "2024-01-10")
    aapl = pd.Series([100, 102, 104, 103, 106, 108, 110.0], index=dates)
    bench = pd.Series([400, 402, 404, 403, 405, 406, 408.0], index=dates)
    fx = pd.Series([1.0] * len(dates), index=dates)  # USD->EUR flat at 1.0

    def fake_download(symbols, **kwargs):
        frames = {}
        for symbol in symbols:
            if symbol == "AAPL":
                frames[("Close", symbol)] = aapl
            elif symbol == "^GSPC":
                frames[("Close", symbol)] = bench
            elif symbol == "USDEUR=X":
                frames[("Close", symbol)] = fx
        df = pd.DataFrame(frames)
        df.columns = pd.MultiIndex.from_tuples(df.columns)
        return df

    monkeypatch.setattr(pa.yf, "download", fake_download)
    monkeypatch.setattr(
        pa.TickerProfileCache,
        "_fetch",
        staticmethod(
            lambda ticker: {
                "currency": "USD",
                "sector": "Technology",
                "country": "United States",
                "name": "Apple Inc",
            }
        ),
    )


def test_analyze_computes_valuation_and_performance(db_session, portfolio, fake_market):
    service = PortfolioAnalyticsService(db_session)
    result = service.analyze(portfolio)

    assert result.market_value == pytest.approx(1100.0)  # 10 * 110 * 1.0
    assert result.cost_basis == pytest.approx(1002.0)
    assert result.unrealized_pnl == pytest.approx(98.0)
    assert result.dividends_received == pytest.approx(5.0)
    assert result.cash_balance == pytest.approx(2000 - 1000 - 2 + 5)

    assert len(result.positions) == 1
    pos = result.positions[0]
    assert pos.ticker == "AAPL"
    assert pos.sector == "Technology"
    assert pos.weight_pct == 100.0

    # Performance series covers the trading days and tracks price moves
    assert result.performance, "expected a performance series"
    first, last = result.performance[0], result.performance[-1]
    assert first.value == pytest.approx(1000.0)  # 10 shares * 100
    assert last.value == pytest.approx(1100.0)
    assert last.cost_basis == pytest.approx(1002.0)

    # TWR: bought at 100 (plus fee flow on day one), ended at 110 -> ~ +10%
    assert result.risk.twr_pct == pytest.approx(10.0, abs=0.5)
    assert result.risk.benchmark_return_pct == pytest.approx(2.0, abs=0.1)
    assert result.risk.volatility_pct is not None
    assert result.risk.max_drawdown_pct is not None

    assert result.sector_allocation[0].label == "Technology"
    assert result.currency_allocation[0].label == "USD"
    # single-position portfolio must be flagged for concentration
    assert any("concentration" in f.lower() for f in result.risk_flags)


def test_summarize_without_quotes_is_offline(db_session, portfolio):
    service = PortfolioAnalyticsService(db_session)
    summary = service.summarize(portfolio, with_quotes=False)
    assert summary.position_count == 1
    assert summary.transaction_count == 3
    assert summary.market_value is None
