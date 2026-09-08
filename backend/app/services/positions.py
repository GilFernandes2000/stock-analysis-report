"""Pure position/cash computation from an ordered transaction stream.

Average-cost method, fees capitalized into cost basis on buys and deducted
from proceeds on sells. All amounts are in the portfolio base currency
(`Transaction.amount` is the signed cash impact excluding fees).
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.models.portfolio import (
    TXN_BUY,
    TXN_DEPOSIT,
    TXN_DIVIDEND,
    TXN_FEE,
    TXN_INTEREST,
    TXN_SELL,
    TXN_TAX,
    TXN_WITHDRAWAL,
    Transaction,
)


@dataclass
class PositionState:
    ticker: str
    isin: str | None = None
    name: str | None = None
    shares: float = 0.0
    cost_basis: float = 0.0
    realized_pnl: float = 0.0
    dividends: float = 0.0
    fees: float = 0.0
    first_bought: datetime | None = None
    last_activity: datetime | None = None
    # Entry price in the instrument's own currency (from Transaction.price):
    # weighted average of buy lots that carried a native price + currency.
    native_currency: str | None = None
    native_cost: float = 0.0
    native_shares: float = 0.0

    @property
    def avg_cost(self) -> float:
        return self.cost_basis / self.shares if self.shares > 1e-9 else 0.0

    @property
    def native_avg_cost(self) -> float | None:
        if self.native_shares <= 1e-9:
            return None
        return self.native_cost / self.native_shares

    @property
    def is_open(self) -> bool:
        return self.shares > 1e-9


@dataclass
class CashFlows:
    deposits: float = 0.0
    withdrawals: float = 0.0
    dividends: float = 0.0
    interest: float = 0.0
    fees: float = 0.0
    taxes: float = 0.0
    buys: float = 0.0
    sells: float = 0.0
    warnings: list[str] = field(default_factory=list)

    @property
    def invested(self) -> float:
        return self.buys - self.sells

    @property
    def cash_balance(self) -> float:
        return (
            self.deposits
            - self.withdrawals
            + self.sells
            - self.buys
            + self.dividends
            + self.interest
            - self.fees
            - self.taxes
        )


def _accrue_native_cost(
    pos: PositionState, txn: Transaction, shares: float, flows: CashFlows
) -> None:
    """Add a buy lot to the position's native-currency cost, if it has one."""
    price = txn.price
    # Keep the raw code: minor-unit currencies (GBp, GBX, ILA, ZAc) are
    # case-sensitive for minor_divisor()/major_currency() downstream.
    currency = (txn.currency or "").strip() or None
    if not price or not currency or shares <= 0:
        return
    if pos.native_currency is None:
        pos.native_currency = currency
    elif currency != pos.native_currency:
        flows.warnings.append(
            f"{pos.ticker}: buy in {currency} differs from {pos.native_currency}; "
            "excluded from the native entry price."
        )
        return
    pos.native_cost += price * shares
    pos.native_shares += shares


def compute_positions(
    transactions: list[Transaction],
) -> tuple[dict[str, PositionState], CashFlows]:
    """Replay transactions chronologically into per-ticker positions."""
    positions: dict[str, PositionState] = {}
    flows = CashFlows()

    for txn in sorted(transactions, key=lambda t: (t.date, t.id or 0)):
        key = (txn.ticker or txn.isin or "?").upper()
        fees = txn.fees or 0.0
        amount = txn.amount or 0.0

        if txn.type in (TXN_BUY, TXN_SELL, TXN_DIVIDEND) and key != "?":
            pos = positions.setdefault(
                key, PositionState(ticker=key, isin=txn.isin, name=txn.name)
            )
            pos.last_activity = txn.date
            if txn.name and not pos.name:
                pos.name = txn.name
            if txn.isin and not pos.isin:
                pos.isin = txn.isin

        if txn.type == TXN_BUY:
            shares = abs(txn.shares or 0.0)
            cost = abs(amount) + fees
            pos = positions[key]
            pos.shares += shares
            pos.cost_basis += cost
            pos.fees += fees
            if pos.first_bought is None:
                pos.first_bought = txn.date
            _accrue_native_cost(pos, txn, shares, flows)
            flows.buys += abs(amount)
            flows.fees += fees

        elif txn.type == TXN_SELL:
            shares = abs(txn.shares or 0.0)
            proceeds = abs(amount) - fees
            pos = positions[key]
            sold = min(shares, pos.shares)
            if shares > pos.shares + 1e-6:
                flows.warnings.append(
                    f"{key}: sold {shares:g} shares but only {pos.shares:g} held "
                    "(missing earlier buys?)"
                )
            avg = pos.avg_cost
            pos.realized_pnl += proceeds - avg * sold
            pos.cost_basis -= avg * sold
            if pos.native_shares > 1e-9 and pos.shares > 1e-9:
                keep = max(0.0, 1.0 - sold / pos.shares)
                pos.native_cost *= keep
                pos.native_shares *= keep
            pos.shares = max(pos.shares - shares, 0.0)
            if pos.shares <= 1e-9:
                pos.cost_basis = 0.0
                pos.native_cost = 0.0
                pos.native_shares = 0.0
            pos.fees += fees
            flows.sells += abs(amount)
            flows.fees += fees

        elif txn.type == TXN_DIVIDEND:
            net = amount - fees  # fees here = withholding tax if recorded that way
            if key != "?":
                positions[key].dividends += net
            flows.dividends += net

        elif txn.type == TXN_DEPOSIT:
            flows.deposits += abs(amount)

        elif txn.type == TXN_WITHDRAWAL:
            flows.withdrawals += abs(amount)

        elif txn.type == TXN_INTEREST:
            flows.interest += amount

        elif txn.type == TXN_FEE:
            flows.fees += abs(amount) + fees

        elif txn.type == TXN_TAX:
            flows.taxes += abs(amount)

    return positions, flows
