from datetime import datetime

from app.models.portfolio import Transaction
from app.services.positions import compute_positions


def _txn(
    type: str,
    date: str,
    ticker: str | None = None,
    shares: float | None = None,
    amount: float = 0.0,
    fees: float = 0.0,
) -> Transaction:
    return Transaction(
        portfolio_id=1,
        type=type,
        date=datetime.fromisoformat(date),
        ticker=ticker,
        shares=shares,
        amount=amount,
        fees=fees,
    )


def test_buy_sell_average_cost_and_realized_pnl():
    txns = [
        _txn("buy", "2024-01-02", "AAPL", 10, -1380.0, 2.0),  # cost 1382, avg 138.2
        _txn("sell", "2024-03-15", "AAPL", 4, 630.0, 2.0),  # proceeds 628
    ]
    positions, flows = compute_positions(txns)
    pos = positions["AAPL"]
    assert pos.shares == 6
    assert abs(pos.avg_cost - 138.2) < 1e-6
    assert abs(pos.realized_pnl - (628 - 138.2 * 4)) < 1e-6
    assert abs(pos.cost_basis - 138.2 * 6) < 1e-6
    assert flows.fees == 4.0


def test_full_sale_closes_position():
    txns = [
        _txn("buy", "2024-01-02", "TSLA", 5, -1000.0),
        _txn("sell", "2024-02-02", "TSLA", 5, 1200.0),
    ]
    positions, _ = compute_positions(txns)
    pos = positions["TSLA"]
    assert not pos.is_open
    assert pos.cost_basis == 0.0
    assert abs(pos.realized_pnl - 200.0) < 1e-6


def test_oversell_is_clamped_with_warning():
    txns = [
        _txn("buy", "2024-01-02", "AAPL", 2, -300.0),
        _txn("sell", "2024-02-02", "AAPL", 5, 800.0),
    ]
    positions, flows = compute_positions(txns)
    assert positions["AAPL"].shares == 0.0
    assert any("AAPL" in w for w in flows.warnings)


def test_dividends_and_cash_flows():
    txns = [
        _txn("deposit", "2024-01-01", amount=5000.0),
        _txn("buy", "2024-01-02", "AAPL", 10, -1380.0, 2.0),
        _txn("dividend", "2024-04-01", "AAPL", amount=12.0),
        _txn("fee", "2024-05-01", amount=-2.5),
        _txn("interest", "2024-06-01", amount=1.5),
        _txn("withdrawal", "2024-06-15", amount=-100.0),
    ]
    positions, flows = compute_positions(txns)
    assert abs(positions["AAPL"].dividends - 12.0) < 1e-6
    assert flows.deposits == 5000.0
    assert flows.withdrawals == 100.0
    # 5000 - 100 - 1380 + 12 + 1.5 - (2 buy fee + 2.5 standalone fee)
    assert abs(flows.cash_balance - (5000 - 100 - 1380 + 12 + 1.5 - 4.5)) < 1e-6


def test_transactions_processed_in_date_order():
    txns = [
        _txn("sell", "2024-03-01", "MSFT", 5, 2000.0),
        _txn("buy", "2024-01-01", "MSFT", 10, -3000.0),
    ]
    positions, flows = compute_positions(txns)
    pos = positions["MSFT"]
    assert pos.shares == 5
    assert not flows.warnings
    assert abs(pos.realized_pnl - (2000 - 300 * 5)) < 1e-6
