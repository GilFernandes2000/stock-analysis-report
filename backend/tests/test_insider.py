from datetime import datetime

from app.services.insider import (
    analyze_insider_activity,
    parse_finviz_rows,
)

NOW = datetime(2026, 7, 24)


def _row(insider, relationship, transaction, value, date):
    return {
        "Insider Trading": insider,
        "Relationship": relationship,
        "Transaction": transaction,
        "Value ($)": value,
        "#Shares": "1,000",
        "Date": date,
    }


def test_parse_rows_classification_and_dates():
    trades = parse_finviz_rows(
        [
            _row("Cook Tim", "Chief Executive Officer", "Buy", "1,234,567", "Jun 15 '26"),
            _row("Doe Jane", "Director", "Sale", "500,000", "May 01 '26"),
            _row("Roe Rick", "EVP", "Option Exercise", "250,000", "Apr 10 '26"),
        ],
        now=NOW,
    )
    assert [t.action for t in trades] == ["buy", "sell", "option"]
    assert trades[0].value == 1234567
    assert trades[0].date == datetime(2026, 6, 15)
    assert trades[0].is_senior
    assert not trades[1].is_senior


def test_cluster_buying_is_bullish():
    trades = parse_finviz_rows(
        [
            _row("Cook Tim", "Chief Executive Officer", "Buy", "800,000", "Jul 01 '26"),
            _row("Smith Ann", "Director", "Buy", "300,000", "Jun 20 '26"),
            _row("Lee Bo", "Chief Financial Officer", "Buy", "200,000", "Jun 05 '26"),
        ],
        now=NOW,
    )
    signal = analyze_insider_activity(trades, now=NOW)
    assert signal.label == "Bullish"
    assert signal.buyers == 3
    assert any("Cluster buying" in s for s in signal.signals)
    assert any("Senior executive" in s for s in signal.signals)


def test_broad_one_sided_selling_is_bearish():
    trades = parse_finviz_rows(
        [
            _row("A", "Director", "Sale", "4,000,000", "Jul 10 '26"),
            _row("B", "EVP", "Sale", "2,500,000", "Jun 28 '26"),
            _row("C", "Chief Executive Officer", "Sale", "9,000,000", "Jun 15 '26"),
            _row("D", "10% Owner", "Sale", "1,000,000", "May 30 '26"),
        ],
        now=NOW,
    )
    signal = analyze_insider_activity(trades, now=NOW)
    assert signal.label == "Bearish"
    assert signal.sellers == 4
    assert signal.sell_value == 16_500_000
    assert any("distribution" in s.lower() for s in signal.signals)


def test_isolated_sale_stays_neutral():
    trades = parse_finviz_rows(
        [_row("Doe Jane", "Director", "Sale", "400,000", "Jun 01 '26")],
        now=NOW,
    )
    signal = analyze_insider_activity(trades, now=NOW)
    assert signal.label == "Neutral"
    assert any("routine" in s for s in signal.signals)


def test_option_exercises_only_are_not_directional():
    trades = parse_finviz_rows(
        [
            _row("Roe Rick", "EVP", "Option Exercise", "250,000", "Jun 10 '26"),
            _row("Poe Pat", "SVP", "Option Exercise", "150,000", "May 12 '26"),
        ],
        now=NOW,
    )
    signal = analyze_insider_activity(trades, now=NOW)
    assert signal.label == "Neutral"
    assert any("compensation" in s for s in signal.signals)


def test_old_trades_fall_outside_window():
    trades = parse_finviz_rows(
        [_row("Cook Tim", "Chief Executive Officer", "Buy", "5,000,000", "Jan 05 '25")],
        now=NOW,
    )
    signal = analyze_insider_activity(trades, now=NOW)
    assert signal.label == "No activity"
    assert signal.buy_count == 0


def test_empty_rows():
    signal = analyze_insider_activity([], now=NOW)
    assert signal.label == "No activity"
    assert signal.summary
