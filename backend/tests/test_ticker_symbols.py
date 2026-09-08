
from app.services.technical_indicators import (
    compute_rsi,
    performance_pct,
    price_vs_sma_pct,
    sma,
)
from app.services.ticker_symbols import (
    has_exchange_suffix,
    is_likely_european,
    is_valid_ticker,
    resolve_ticker_candidates,
)


def test_valid_tickers():
    assert is_valid_ticker("AAPL")
    assert is_valid_ticker("SAP.DE")
    assert is_valid_ticker("NOVO-B.CO")
    assert not is_valid_ticker("")


def test_european_detection():
    assert has_exchange_suffix("SAP.DE")
    assert has_exchange_suffix("VOD.L")
    assert not has_exchange_suffix("AAPL")
    assert is_likely_european("BMW")
    assert is_likely_european("SAP.DE")
    assert not is_likely_european("AAPL")


def test_resolve_candidates():
    assert resolve_ticker_candidates("bmw") == ["BMW", "BMW.DE"]
    assert resolve_ticker_candidates("SAP.DE") == ["SAP.DE"]
    assert resolve_ticker_candidates("AAPL") == ["AAPL"]


def test_rsi_and_sma():
    closes = [float(i) for i in range(1, 40)]
    assert compute_rsi(closes) is not None
    assert sma(closes, 20) is not None
    assert price_vs_sma_pct(110.0, 100.0) == 10.0
    assert performance_pct(closes, 5) is not None
