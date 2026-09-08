"""Portfolio analytics: valuation, performance series, risk metrics, allocation.

Prices come from one batched yfinance download (tickers + benchmark + FX pairs).
Per-ticker profile data (currency, sector, country) is cached in api_cache.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from app.models.cache import ApiCache
from app.models.portfolio import (
    TXN_BUY,
    TXN_DEPOSIT,
    TXN_SELL,
    TXN_WITHDRAWAL,
    Portfolio,
    Transaction,
)
from app.schemas.portfolio import (
    AllocationSlice,
    CashFlowSummary,
    ClosedPositionResponse,
    ContributorEntry,
    PerformancePoint,
    PortfolioAnalyticsResponse,
    PortfolioSummary,
    PositionResponse,
    RiskMetrics,
)
from app.services.positions import CashFlows, PositionState, compute_positions

logger = logging.getLogger(__name__)

PROFILE_CACHE_TTL = timedelta(days=7)
TRADING_DAYS = 252

# Exchange suffix -> instrument currency fallback
SUFFIX_CURRENCY: dict[str, str] = {
    ".L": "GBp",
    ".DE": "EUR", ".AS": "EUR", ".PA": "EUR", ".MI": "EUR", ".MC": "EUR",
    ".BR": "EUR", ".VI": "EUR", ".HE": "EUR", ".IR": "EUR", ".LS": "EUR",
    ".F": "EUR", ".BE": "EUR",
    ".SW": "CHF", ".CO": "DKK", ".ST": "SEK", ".OL": "NOK",
    ".TO": "CAD", ".AX": "AUD",
}


def _suffix_currency(ticker: str) -> str:
    upper = ticker.upper()
    for suffix, currency in SUFFIX_CURRENCY.items():
        if upper.endswith(suffix):
            return currency
    return "USD"


def _minor_divisor(currency: str | None) -> float:
    return 100.0 if currency in ("GBp", "GBX", "ILA", "ZAc") else 1.0


def _major(currency: str | None) -> str:
    mapping = {"GBp": "GBP", "GBX": "GBP", "ILA": "ILS", "ZAc": "ZAR"}
    if not currency:
        return "USD"
    return mapping.get(currency, currency.upper())


class TickerProfileCache:
    """sector/country/currency/name per ticker, cached in api_cache."""

    def __init__(self, db: Session):
        self.db = db

    def get(self, ticker: str) -> dict:
        key = f"tickerprofile:{ticker.upper()}"
        row = self.db.query(ApiCache).filter(ApiCache.cache_key == key).first()
        if row and datetime.utcnow() - row.created_at <= PROFILE_CACHE_TTL:
            return json.loads(row.payload)

        profile = self._fetch(ticker)
        payload = json.dumps(profile)
        if row:
            row.payload = payload
            row.created_at = datetime.utcnow()
        else:
            self.db.add(ApiCache(cache_key=key, payload=payload))
        self.db.commit()
        return profile

    @staticmethod
    def _fetch(ticker: str) -> dict:
        try:
            info = yf.Ticker(ticker).info or {}
            return {
                "currency": info.get("currency"),
                "sector": info.get("sector"),
                "country": info.get("country"),
                "name": info.get("longName") or info.get("shortName"),
                "quote_type": info.get("quoteType"),
                "market_cap": info.get("marketCap"),
                "pe": info.get("trailingPE"),
            }
        except Exception as exc:
            logger.warning("Profile fetch failed for %s: %s", ticker, exc)
            return {"currency": None, "sector": None, "country": None, "name": None}


class PortfolioAnalyticsService:
    def __init__(self, db: Session):
        self.db = db
        self.profiles = TickerProfileCache(db)

    # ------------------------------------------------------------------
    # Hub summary (cheap unless with_quotes)
    # ------------------------------------------------------------------

    def summarize(self, portfolio: Portfolio, with_quotes: bool = False) -> PortfolioSummary:
        txns = portfolio.transactions
        positions, flows = compute_positions(txns)
        open_positions = [p for p in positions.values() if p.is_open]

        summary = PortfolioSummary(
            id=portfolio.id,
            name=portfolio.name,
            broker=portfolio.broker,
            base_currency=portfolio.base_currency,
            benchmark=portfolio.benchmark,
            created_at=portfolio.created_at,
            transaction_count=len(txns),
            position_count=len(open_positions),
        )
        if not with_quotes or not open_positions:
            return summary

        try:
            tickers = [p.ticker for p in open_positions]
            prices, day_change = self._last_prices(tickers, portfolio.base_currency)
            market_value = 0.0
            weighted_change = 0.0
            for pos in open_positions:
                price = prices.get(pos.ticker)
                if price is None:
                    continue
                value = pos.shares * price
                market_value += value
                weighted_change += (day_change.get(pos.ticker) or 0.0) * value
            realized_total = sum(p.realized_pnl for p in positions.values())
            dividends_total = sum(p.dividends for p in positions.values())
            cost_open = sum(p.cost_basis for p in open_positions)
            summary.market_value = round(market_value, 2)
            summary.total_return = round(
                market_value - cost_open + realized_total + dividends_total, 2
            )
            invested = flows.invested if flows.invested > 0 else cost_open
            summary.total_return_pct = (
                round(summary.total_return / invested * 100, 2) if invested else None
            )
            summary.day_change_pct = (
                round(weighted_change / market_value, 2) if market_value else None
            )
        except Exception as exc:
            logger.warning("Quote summary failed for portfolio %s: %s", portfolio.id, exc)
        return summary

    def _last_prices(
        self, tickers: list[str], base_currency: str
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Latest close per ticker converted to base currency + day change %."""
        currencies = {t: self._ticker_currency(t) for t in tickers}
        fx_pairs = self._fx_pairs(currencies.values(), base_currency)
        symbols = list(dict.fromkeys(tickers + fx_pairs))
        data = yf.download(
            symbols, period="10d", interval="1d", progress=False,
            auto_adjust=False, group_by="column", threads=True,
        )
        closes = self._extract_closes(data, symbols)
        prices: dict[str, float] = {}
        changes: dict[str, float] = {}
        for ticker in tickers:
            series = closes.get(ticker)
            if series is None or series.dropna().empty:
                continue
            clean = series.dropna()
            native = float(clean.iloc[-1]) / _minor_divisor(currencies[ticker])
            rate = self._fx_last(closes, currencies[ticker], base_currency)
            prices[ticker] = native * rate
            if len(clean) >= 2 and float(clean.iloc[-2]):
                changes[ticker] = (float(clean.iloc[-1]) / float(clean.iloc[-2]) - 1) * 100
        return prices, changes

    # ------------------------------------------------------------------
    # Full analytics
    # ------------------------------------------------------------------

    def analyze(self, portfolio: Portfolio) -> PortfolioAnalyticsResponse:
        txns = sorted(portfolio.transactions, key=lambda t: (t.date, t.id or 0))
        positions, flows = compute_positions(txns)
        base = portfolio.base_currency
        open_positions = sorted(
            (p for p in positions.values() if p.is_open),
            key=lambda p: p.cost_basis,
            reverse=True,
        )
        closed = [p for p in positions.values() if not p.is_open]
        stale = False

        # --- price history (single batch download) ---
        tickers = [p.ticker for p in open_positions]
        all_traded = sorted({p.ticker for p in positions.values()})
        currencies = {t: self._ticker_currency(t) for t in all_traded}
        start = txns[0].date if txns else datetime.utcnow() - timedelta(days=30)
        closes: dict[str, pd.Series] = {}
        if all_traded or portfolio.benchmark:
            fx_pairs = self._fx_pairs(currencies.values(), base)
            symbols = list(dict.fromkeys(all_traded + fx_pairs + [portfolio.benchmark]))
            try:
                data = yf.download(
                    symbols, start=start.date() - timedelta(days=7), interval="1d",
                    progress=False, auto_adjust=False, group_by="column", threads=True,
                )
                closes = self._extract_closes(data, symbols)
            except Exception as exc:
                logger.warning("History download failed: %s", exc)
                stale = True

        # --- daily valuation ---
        performance, risk = self._performance_series(
            txns, currencies, closes, portfolio.benchmark, base
        )

        # --- position enrichment ---
        profiles = {t: self.profiles.get(t) for t in tickers}
        position_rows: list[PositionResponse] = []
        market_value = 0.0
        day_change_value = 0.0
        prev_value = 0.0
        for pos in open_positions:
            series = closes.get(pos.ticker)
            native_price = None
            price_base = None
            day_pct = None
            if series is not None and not series.dropna().empty:
                clean = series.dropna()
                divisor = _minor_divisor(currencies.get(pos.ticker))
                native_price = float(clean.iloc[-1]) / divisor
                rate = self._fx_last(closes, currencies.get(pos.ticker), base)
                price_base = native_price * rate
                if len(clean) >= 2 and float(clean.iloc[-2]):
                    day_pct = (float(clean.iloc[-1]) / float(clean.iloc[-2]) - 1) * 100
            else:
                stale = True

            value = pos.shares * price_base if price_base is not None else None
            if value is not None:
                market_value += value
                if day_pct is not None:
                    day_change_value += value - value / (1 + day_pct / 100)
                    prev_value += value / (1 + day_pct / 100)
                else:
                    prev_value += value
            profile = profiles.get(pos.ticker) or {}
            unrealized = value - pos.cost_basis if value is not None else None
            position_rows.append(
                PositionResponse(
                    ticker=pos.ticker,
                    name=profile.get("name") or pos.name,
                    isin=pos.isin,
                    shares=round(pos.shares, 6),
                    avg_cost=round(pos.avg_cost, 4),
                    cost_basis=round(pos.cost_basis, 2),
                    current_price=round(price_base, 4) if price_base is not None else None,
                    native_price=round(native_price, 4) if native_price is not None else None,
                    native_currency=_major(currencies.get(pos.ticker)),
                    market_value=round(value, 2) if value is not None else None,
                    unrealized_pnl=round(unrealized, 2) if unrealized is not None else None,
                    unrealized_pnl_pct=round(unrealized / pos.cost_basis * 100, 2)
                    if unrealized is not None and pos.cost_basis
                    else None,
                    realized_pnl=round(pos.realized_pnl, 2),
                    dividends=round(pos.dividends, 2),
                    fees=round(pos.fees, 2),
                    day_change_pct=round(day_pct, 2) if day_pct is not None else None,
                    sector=profile.get("sector"),
                    country=profile.get("country"),
                    first_bought=pos.first_bought,
                )
            )

        for row in position_rows:
            if row.market_value is not None and market_value:
                row.weight_pct = round(row.market_value / market_value * 100, 2)

        # --- aggregates ---
        cost_open = sum(p.cost_basis for p in open_positions)
        realized_total = sum(p.realized_pnl for p in positions.values())
        dividends_total = sum(p.dividends for p in positions.values())
        unrealized_total = market_value - cost_open
        fees_total = flows.fees
        total_return = unrealized_total + realized_total + dividends_total + flows.interest - fees_total - flows.taxes
        invested_ref = flows.invested if flows.invested > 0 else cost_open

        # --- allocations ---
        sector_alloc = self._allocate(position_rows, market_value, lambda r: r.sector or "Unknown")
        country_alloc = self._allocate(position_rows, market_value, lambda r: r.country or "Unknown")
        currency_alloc = self._allocate(
            position_rows, market_value, lambda r: r.native_currency or "?"
        )

        # --- contributors ---
        contributions: list[ContributorEntry] = []
        for pos in positions.values():
            row = next((r for r in position_rows if r.ticker == pos.ticker), None)
            unrealized = row.unrealized_pnl if row and row.unrealized_pnl is not None else 0.0
            total = unrealized + pos.realized_pnl + pos.dividends - pos.fees
            invested = pos.cost_basis + (
                abs(pos.realized_pnl) if not pos.is_open else 0.0
            )
            denom = pos.cost_basis if pos.is_open else None
            contributions.append(
                ContributorEntry(
                    ticker=pos.ticker,
                    name=(row.name if row else None) or pos.name,
                    total_pnl=round(total, 2),
                    return_pct=round(total / denom * 100, 2) if denom else None,
                )
            )
        contributions.sort(key=lambda c: c.total_pnl, reverse=True)
        top_contributors = [c for c in contributions if c.total_pnl > 0][:5]
        top_detractors = [c for c in reversed(contributions) if c.total_pnl < 0][:5]

        # --- risk flags ---
        risk_flags = self._risk_flags(position_rows, sector_alloc, currency_alloc, risk)
        risk_flags.extend(flows.warnings)

        return PortfolioAnalyticsResponse(
            portfolio_id=portfolio.id,
            name=portfolio.name,
            base_currency=base,
            benchmark=portfolio.benchmark,
            as_of=datetime.utcnow(),
            market_value=round(market_value, 2),
            cost_basis=round(cost_open, 2),
            cash_balance=round(flows.cash_balance, 2),
            total_value=round(market_value + max(flows.cash_balance, 0.0), 2),
            unrealized_pnl=round(unrealized_total, 2),
            unrealized_pnl_pct=round(unrealized_total / cost_open * 100, 2) if cost_open else None,
            realized_pnl=round(realized_total, 2),
            dividends_received=round(dividends_total, 2),
            fees_paid=round(fees_total, 2),
            total_return=round(total_return, 2),
            total_return_pct=round(total_return / invested_ref * 100, 2) if invested_ref else None,
            day_change=round(day_change_value, 2) if prev_value else None,
            day_change_pct=round(day_change_value / prev_value * 100, 2) if prev_value else None,
            positions=position_rows,
            closed_positions=[
                ClosedPositionResponse(
                    ticker=p.ticker,
                    name=p.name,
                    realized_pnl=round(p.realized_pnl, 2),
                    dividends=round(p.dividends, 2),
                    fees=round(p.fees, 2),
                )
                for p in sorted(closed, key=lambda p: p.realized_pnl, reverse=True)
            ],
            sector_allocation=sector_alloc,
            currency_allocation=currency_alloc,
            country_allocation=country_alloc,
            performance=performance,
            risk=risk,
            top_contributors=top_contributors,
            top_detractors=top_detractors,
            cash_flows=CashFlowSummary(
                deposits=round(flows.deposits, 2),
                withdrawals=round(flows.withdrawals, 2),
                dividends=round(flows.dividends, 2),
                interest=round(flows.interest, 2),
                fees=round(flows.fees, 2),
                taxes=round(flows.taxes, 2),
                invested=round(flows.invested, 2),
                cash_balance=round(flows.cash_balance, 2),
            ),
            risk_flags=risk_flags,
            stale=stale,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ticker_currency(self, ticker: str) -> str:
        # The quote currency must come from the instrument itself: a trade can
        # settle in EUR while the resolved Yahoo listing quotes in GBp (VUSA).
        profile = self.profiles.get(ticker)
        if profile.get("currency"):
            return profile["currency"]
        txn = (
            self.db.query(Transaction)
            .filter(Transaction.ticker == ticker, Transaction.currency.isnot(None))
            .order_by(Transaction.date.desc())
            .first()
        )
        if txn and txn.currency:
            return txn.currency
        return _suffix_currency(ticker)

    @staticmethod
    def _fx_pairs(currencies, base: str) -> list[str]:
        pairs = []
        for currency in set(currencies):
            major = _major(currency)
            if major and major != base:
                pairs.append(f"{major}{base}=X")
        return pairs

    @staticmethod
    def _extract_closes(data: pd.DataFrame, symbols: list[str]) -> dict[str, pd.Series]:
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

    def _fx_last(
        self, closes: dict[str, pd.Series], currency: str | None, base: str
    ) -> float:
        major = _major(currency)
        if major == base:
            return 1.0
        series = closes.get(f"{major}{base}=X")
        if series is not None and not series.dropna().empty:
            return float(series.dropna().iloc[-1])
        return 1.0

    def _performance_series(
        self,
        txns: list[Transaction],
        currencies: dict[str, str],
        closes: dict[str, pd.Series],
        benchmark: str,
        base: str,
    ) -> tuple[list[PerformancePoint], RiskMetrics]:
        trade_txns = [t for t in txns if t.type in (TXN_BUY, TXN_SELL) and t.ticker]
        if not trade_txns or not closes:
            return [], RiskMetrics()

        tickers = sorted({t.ticker for t in trade_txns})
        price_frame = pd.DataFrame(
            {t: closes[t] for t in tickers if t in closes}
        ).ffill()
        if price_frame.empty:
            return [], RiskMetrics()
        price_frame = price_frame[price_frame.index >= pd.Timestamp(trade_txns[0].date.date())]
        if price_frame.empty:
            return [], RiskMetrics()

        # FX frame aligned to price dates
        fx_frame = pd.DataFrame(index=price_frame.index)
        for ticker in price_frame.columns:
            major = _major(currencies.get(ticker))
            if major == base:
                fx_frame[ticker] = 1.0
            else:
                series = closes.get(f"{major}{base}=X")
                if series is not None:
                    fx_frame[ticker] = series.reindex(price_frame.index).ffill().bfill()
                else:
                    fx_frame[ticker] = 1.0
        divisors = {
            t: _minor_divisor(currencies.get(t)) for t in price_frame.columns
        }

        # Shares held per day (event-based cumulative)
        shares = pd.DataFrame(0.0, index=price_frame.index, columns=price_frame.columns)
        daily_flows = pd.Series(0.0, index=price_frame.index)  # invested cash per day
        external_flows = pd.Series(0.0, index=price_frame.index)
        cum_invested = pd.Series(0.0, index=price_frame.index)
        invested_events: list[tuple[pd.Timestamp, float]] = []
        for txn in trade_txns:
            day = pd.Timestamp(txn.date.date())
            pos = price_frame.index.searchsorted(day)
            if pos >= len(price_frame.index):
                continue
            day_key = price_frame.index[pos]
            qty = abs(txn.shares or 0.0)
            if txn.ticker not in shares.columns:
                continue
            if txn.type == TXN_BUY:
                shares.loc[day_key:, txn.ticker] += qty
                cash = abs(txn.amount) + (txn.fees or 0.0)
                daily_flows[day_key] += cash
                invested_events.append((day_key, cash))
            else:
                shares.loc[day_key:, txn.ticker] -= qty
                cash = abs(txn.amount) - (txn.fees or 0.0)
                daily_flows[day_key] -= cash
                invested_events.append((day_key, -cash))
        for day, cash in invested_events:
            cum_invested[day:] = cum_invested[day:] + cash
        for txn in txns:
            if txn.type in (TXN_DEPOSIT, TXN_WITHDRAWAL):
                day = pd.Timestamp(txn.date.date())
                pos = price_frame.index.searchsorted(day)
                if pos < len(price_frame.index):
                    external_flows[price_frame.index[pos]] += txn.amount

        native = price_frame / pd.Series(divisors)
        value_series = (shares * native * fx_frame).sum(axis=1)
        value_series = value_series[value_series.index >= value_series[value_series > 0].index.min()]
        if value_series.empty:
            return [], RiskMetrics()
        cum_invested = cum_invested.reindex(value_series.index)
        daily_flows = daily_flows.reindex(value_series.index).fillna(0.0)

        # Time-weighted return index
        twr_index = pd.Series(index=value_series.index, dtype=float)
        returns: list[float] = []
        index_value = 100.0
        prev = None
        for day in value_series.index:
            value = float(value_series[day])
            flow = float(daily_flows[day])
            if prev is not None and prev > 0:
                r = (value - flow - prev) / prev
                returns.append(r)
                index_value *= 1 + r
            twr_index[day] = index_value
            prev = value

        # Benchmark indexed to 100
        bench_series = closes.get(benchmark)
        bench_indexed = None
        bench_returns = None
        if bench_series is not None and not bench_series.dropna().empty:
            aligned = bench_series.reindex(value_series.index).ffill().bfill()
            if not aligned.dropna().empty and float(aligned.iloc[0]):
                bench_indexed = aligned / float(aligned.iloc[0]) * 100.0
                bench_returns = aligned.pct_change().dropna()

        # Risk metrics
        risk = RiskMetrics()
        if returns:
            ret = pd.Series(returns)
            std = float(ret.std())
            mean = float(ret.mean())
            risk.volatility_pct = round(std * math.sqrt(TRADING_DAYS) * 100, 2)
            if std > 0:
                risk.sharpe = round(mean / std * math.sqrt(TRADING_DAYS), 2)
            drawdown = twr_index / twr_index.cummax() - 1
            risk.max_drawdown_pct = round(float(drawdown.min()) * 100, 2)
            risk.twr_pct = round(float(twr_index.iloc[-1]) - 100.0, 2)
            risk.best_day_pct = round(float(ret.max()) * 100, 2)
            risk.worst_day_pct = round(float(ret.min()) * 100, 2)
            if bench_returns is not None and len(bench_returns) > 2:
                port_ret = pd.Series(returns, index=value_series.index[1 : len(returns) + 1])
                joined = pd.concat([port_ret, bench_returns], axis=1, join="inner").dropna()
                if len(joined) > 2 and float(joined.iloc[:, 1].var()):
                    risk.beta = round(
                        float(joined.iloc[:, 0].cov(joined.iloc[:, 1]))
                        / float(joined.iloc[:, 1].var()),
                        2,
                    )
        if bench_indexed is not None:
            risk.benchmark_return_pct = round(float(bench_indexed.iloc[-1]) - 100.0, 2)

        # Downsample long series for the API payload (~weekly beyond 2y)
        points: list[PerformancePoint] = []
        index = value_series.index
        step = 1
        if len(index) > 900:
            step = math.ceil(len(index) / 900)
        for i, day in enumerate(index):
            if step > 1 and i % step != 0 and i != len(index) - 1:
                continue
            points.append(
                PerformancePoint(
                    date=day.strftime("%Y-%m-%d"),
                    value=round(float(value_series[day]), 2),
                    cost_basis=round(float(cum_invested[day]), 2),
                    benchmark=round(float(bench_indexed[day]), 2)
                    if bench_indexed is not None and not pd.isna(bench_indexed[day])
                    else None,
                    twr_index=round(float(twr_index[day]), 2)
                    if not pd.isna(twr_index[day])
                    else None,
                )
            )
        return points, risk

    @staticmethod
    def _allocate(rows: list[PositionResponse], total: float, key) -> list[AllocationSlice]:
        if not total:
            return []
        buckets: dict[str, float] = {}
        for row in rows:
            if row.market_value is None:
                continue
            label = key(row)
            buckets[label] = buckets.get(label, 0.0) + row.market_value
        return [
            AllocationSlice(
                label=label, value=round(value, 2), weight_pct=round(value / total * 100, 2)
            )
            for label, value in sorted(buckets.items(), key=lambda x: x[1], reverse=True)
        ]

    @staticmethod
    def _risk_flags(
        rows: list[PositionResponse],
        sectors: list[AllocationSlice],
        currency_alloc: list[AllocationSlice],
        risk: RiskMetrics,
    ) -> list[str]:
        flags: list[str] = []
        for row in rows:
            if row.weight_pct is not None and row.weight_pct > 25:
                flags.append(
                    f"{row.ticker} is {row.weight_pct:.1f}% of the portfolio (concentration risk)"
                )
        for alloc in sectors:
            if alloc.label != "Unknown" and alloc.weight_pct > 40:
                flags.append(
                    f"High sector concentration: {alloc.label} at {alloc.weight_pct:.1f}%"
                )
        for alloc in currency_alloc:
            if alloc.label not in ("?",) and alloc.weight_pct > 70 and len(currency_alloc) > 1:
                flags.append(
                    f"{alloc.weight_pct:.1f}% exposure to {alloc.label} (currency risk)"
                )
        if risk.max_drawdown_pct is not None and risk.max_drawdown_pct < -30:
            flags.append(
                f"Max drawdown of {risk.max_drawdown_pct:.1f}% over the holding period"
            )
        if risk.volatility_pct is not None and risk.volatility_pct > 30:
            flags.append(f"Annualized volatility is high ({risk.volatility_pct:.1f}%)")
        return flags
