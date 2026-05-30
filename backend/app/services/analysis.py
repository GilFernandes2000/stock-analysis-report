from typing import Any


def compute_technical_trend(fields: dict[str, float | None]) -> dict[str, Any]:
    score = 0
    signals: list[str] = []

    rsi = fields.get("rsi")
    if rsi is not None:
        if rsi < 30:
            score += 25
            signals.append(f"RSI {rsi:.1f} oversold — potential bounce")
        elif rsi > 70:
            score -= 25
            signals.append(f"RSI {rsi:.1f} overbought — caution")
        else:
            signals.append(f"RSI {rsi:.1f} in neutral zone")

    sma20 = fields.get("sma20")
    sma50 = fields.get("sma50")
    sma200 = fields.get("sma200")

    # Finviz returns SMA fields as % distance: positive = price above SMA
    if sma20 is not None and sma50 is not None and sma200 is not None:
        if sma20 > 0 and sma50 > 0 and sma200 > 0:
            score += 30
            signals.append("Price above SMA20, SMA50, and SMA200 — uptrend")
        elif sma20 < 0 and sma50 < 0 and sma200 < 0:
            score -= 30
            signals.append("Price below SMA20, SMA50, and SMA200 — downtrend")
        elif sma50 > 0 and sma200 > 0:
            score += 15
            signals.append("Price above SMA50 and SMA200")
        elif sma50 < 0 and sma200 < 0:
            score -= 15
            signals.append("Price below SMA50 and SMA200")

    perf_month = fields.get("perf_month")
    perf_quarter = fields.get("perf_quarter")
    if perf_month is not None and perf_quarter is not None:
        if perf_month > 0 and perf_quarter > 0:
            score += 15
            signals.append("Positive month and quarter performance")
        elif perf_month < 0 and perf_quarter < 0:
            score -= 15
            signals.append("Negative month and quarter performance")

    perf_ytd = fields.get("perf_ytd")
    if perf_ytd is not None:
        if perf_ytd > 10:
            score += 10
            signals.append(f"Strong YTD performance ({perf_ytd:.1f}%)")
        elif perf_ytd < -10:
            score -= 10
            signals.append(f"Weak YTD performance ({perf_ytd:.1f}%)")

    if score >= 20:
        label = "Bullish"
    elif score <= -20:
        label = "Bearish"
    else:
        label = "Neutral"

    return {"score": score, "label": label, "signals": signals}


def summarize_stock_for_report(
    ticker: str,
    stock: dict[str, Any],
    trend: dict[str, Any],
    sentiment_label: str,
    inst_own: str | None,
    analyst_upside: float | None,
) -> str:
    rsi = stock.get("RSI (14)", "N/A")
    trend_label = trend["label"]
    inst = inst_own or "N/A"
    upside = f"{analyst_upside:+.1f}%" if analyst_upside is not None else "N/A"
    return (
        f"**{ticker}** — {trend_label} technicals (RSI {rsi}). "
        f"Institutional ownership {inst}. "
        f"News sentiment: {sentiment_label}. "
        f"Analyst median target implies {upside} upside."
    )
