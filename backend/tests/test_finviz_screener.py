from app.services.finviz_client import _fix_screener_row


def test_realigns_row_when_logo_column_present():
    # Finviz injects a logo cell ('Z') before the real ticker 'ZTS', shifting
    # every value one column to the right of its header.
    broken = {
        "No.": "1",
        "Ticker": "Z",
        "Perf Week": "ZTS",
        "Perf Month": "-2.04%",
        "Price": "0.00",
        "Change": "75.00",
        "Volume": "0.58%",
    }
    fixed = _fix_screener_row(broken)
    assert fixed["Ticker"] == "ZTS"
    assert fixed["Perf Week"] == "-2.04%"
    assert fixed["Price"] == "75.00"
    assert fixed["Change"] == "0.58%"


def test_realigns_overview_row_with_company():
    broken = {
        "No.": "1",
        "Ticker": "S",
        "Company": "SAP",
        "Sector": "Sap SE ADR",
        "Price": "0.00",
        "Change": "154.46",
    }
    fixed = _fix_screener_row(broken)
    assert fixed["Ticker"] == "SAP"
    assert fixed["Company"] == "Sap SE ADR"
    assert fixed["Price"] == "154.46"


def test_no_shift_when_already_aligned():
    good = {
        "No.": "1",
        "Ticker": "AAPL",
        "Company": "Apple Inc",
        "Price": "231.00",
        "Change": "1.20%",
    }
    assert _fix_screener_row(good) == good


def test_single_letter_ticker_without_logo_is_untouched():
    # Ford: real single-letter ticker, next column is a company name — must not
    # be mistaken for a logo cell.
    row = {
        "No.": "1",
        "Ticker": "F",
        "Company": "Ford Motor Co",
        "Price": "12.00",
        "Change": "0.50%",
    }
    assert _fix_screener_row(row) == row


def test_single_letter_ticker_with_logo_is_realigned():
    # Visa: logo 'V' then real ticker 'V' then company 'Visa Inc'.
    broken = {
        "No.": "1",
        "Ticker": "V",
        "Company": "V",
        "Sector": "Visa Inc",
        "Price": "0.00",
        "Change": "330.00",
    }
    fixed = _fix_screener_row(broken)
    assert fixed["Ticker"] == "V"
    assert fixed["Company"] == "Visa Inc"
    assert fixed["Price"] == "330.00"


def test_missing_ticker_key_is_safe():
    row = {"No.": "1", "Foo": "bar"}
    assert _fix_screener_row(row) == row
