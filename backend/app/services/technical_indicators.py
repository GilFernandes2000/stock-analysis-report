from __future__ import annotations


def compute_rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None

    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))

    if len(gains) < period:
        return None

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def price_vs_sma_pct(price: float, sma_value: float | None) -> float | None:
    if sma_value is None or sma_value == 0:
        return None
    return round(((price - sma_value) / sma_value) * 100, 2)


def performance_pct(closes: list[float], lookback: int) -> float | None:
    if len(closes) <= lookback:
        return None
    start = closes[-lookback - 1]
    end = closes[-1]
    if start == 0:
        return None
    return round(((end - start) / start) * 100, 2)


def ytd_performance_pct(closes: list[float], dates: list) -> float | None:
    if not closes or not dates:
        return None
    try:
        year = dates[-1].year
        for i, d in enumerate(dates):
            if d.year == year:
                start = closes[i]
                if start == 0:
                    return None
                return round(((closes[-1] - start) / start) * 100, 2)
    except AttributeError:
        return None
    return None
