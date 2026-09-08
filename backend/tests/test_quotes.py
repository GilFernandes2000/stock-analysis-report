import pandas as pd
import pytest

from app.services import quotes as quotes_mod
from app.services.quotes import QuoteService


@pytest.fixture()
def profiles(monkeypatch):
    """Canned ticker profiles keyed by symbol; no network."""
    table: dict[str, dict] = {}
    monkeypatch.setattr(
        "app.services.portfolio_analytics.TickerProfileCache.get",
        lambda self, ticker: table.get(ticker.upper(), {}),
    )
    return table


def _download(frames: dict[str, pd.Series]):
    dates = next(iter(frames.values())).index
    df = pd.DataFrame({("Close", sym): s for sym, s in frames.items()})
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    df.index = dates

    def fake(symbols, **kwargs):
        return df

    return fake


def test_get_quotes_converts_into_display_currency(db_session, profiles, monkeypatch):
    profiles["AAPL"] = {"currency": "USD", "name": "Apple", "sector": "Tech"}
    dates = pd.bdate_range("2024-01-02", periods=3)
    monkeypatch.setattr(
        quotes_mod.yf,
        "download",
        _download(
            {
                "AAPL": pd.Series([180.0, 190.0, 200.0], index=dates),
                "USDEUR=X": pd.Series([0.9, 0.9, 0.9], index=dates),
            }
        ),
    )

    result, stale = QuoteService(db_session).get_quotes(["aapl"], "EUR")

    assert stale is False
    (q,) = result
    assert q.ticker == "AAPL"
    assert q.native_currency == "USD"
    assert q.native_price == 200.0
    assert q.price == pytest.approx(180.0)  # 200 * 0.9
    assert q.change_pct == pytest.approx((200 / 190 - 1) * 100, rel=1e-3)


def test_get_quotes_handles_gbp_minor_unit(db_session, profiles, monkeypatch):
    profiles["VOD.L"] = {"currency": "GBp", "name": "Vodafone"}
    dates = pd.bdate_range("2024-01-02", periods=2)
    monkeypatch.setattr(
        quotes_mod.yf,
        "download",
        _download(
            {
                "VOD.L": pd.Series([7000.0, 7200.0], index=dates),  # pence
                "GBPEUR=X": pd.Series([1.15, 1.15], index=dates),
            }
        ),
    )

    (q,), stale = QuoteService(db_session).get_quotes(["VOD.L"], "EUR")

    assert stale is False
    assert q.native_currency == "GBP"          # normalized from GBp
    assert q.native_price == 72.0              # 7200 pence / 100
    assert q.price == pytest.approx(72.0 * 1.15)


def test_get_quotes_flags_stale_when_download_fails(db_session, profiles, monkeypatch):
    profiles["AAPL"] = {"currency": "USD"}

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(quotes_mod.yf, "download", boom)

    (q,), stale = QuoteService(db_session).get_quotes(["AAPL"], "EUR")

    assert stale is True
    assert q.price is None and q.native_price is None


def test_get_quotes_empty_input(db_session):
    assert QuoteService(db_session).get_quotes([], "EUR") == ([], False)
    assert QuoteService(db_session).get_quotes(["  ", ""], "EUR") == ([], False)
