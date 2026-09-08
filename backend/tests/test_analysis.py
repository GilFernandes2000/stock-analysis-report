
from app.services.analysis import compute_technical_trend


def test_bullish_uptrend():
    fields = {
        "rsi": 55,
        "sma20": 2.0,
        "sma50": 5.0,
        "sma200": 10.0,
        "perf_month": 3.0,
        "perf_quarter": 8.0,
        "perf_ytd": 15.0,
    }
    result = compute_technical_trend(fields)
    assert result["label"] == "Bullish"
    assert result["score"] >= 20


def test_bearish_downtrend():
    fields = {
        "rsi": 75,
        "sma20": -2.0,
        "sma50": -5.0,
        "sma200": -10.0,
        "perf_month": -4.0,
        "perf_quarter": -6.0,
        "perf_ytd": -15.0,
    }
    result = compute_technical_trend(fields)
    assert result["label"] == "Bearish"
    assert result["score"] <= -20


def test_neutral_mixed_signals():
    fields = {
        "rsi": 50,
        "sma20": 1.0,
        "sma50": -1.0,
        "sma200": 0.5,
        "perf_month": 1.0,
        "perf_quarter": -1.0,
    }
    result = compute_technical_trend(fields)
    assert result["label"] == "Neutral"


def test_oversold_adds_bullish_score():
    fields = {"rsi": 25}
    result = compute_technical_trend(fields)
    assert any("oversold" in s.lower() for s in result["signals"])
