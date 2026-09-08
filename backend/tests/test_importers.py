from datetime import datetime

from app.services.importers import (
    IsinResolver,
    _money_pair,
    _parse_number,
    _sniff_delimiter,
    detect_format,
    parse_degiro_account,
    parse_degiro_transactions,
    parse_trading212,
)

DEGIRO_TRANSACTIONS = """Date,Time,Product,ISIN,Exchange,Execution venue,Quantity,Price,,Local value,,Value,,Exchange rate,Transaction and/or third party fees,,Total,,Order ID
02-01-2024,09:30,APPLE INC,US0378331005,NDQ,XNAS,10,150.00,USD,-1500.00,USD,-1380.00,EUR,1.0870,-2.00,EUR,-1382.00,EUR,ord-0001
15-03-2024,10:00,APPLE INC,US0378331005,NDQ,XNAS,-4,170.00,USD,680.00,USD,630.00,EUR,1.0794,-2.00,EUR,628.00,EUR,ord-0002
20-02-2024,14:20,ASML HOLDING NV,NL0010273215,EAM,XAMS,2,600.00,EUR,-1200.00,EUR,-1200.00,EUR,,-1.00,EUR,-1201.00,EUR,ord-0003
"""

DEGIRO_ACCOUNT = """Date,Time,Value date,Product,ISIN,Description,FX,Change,,Balance,,Order ID
01-01-2024,10:00,01-01-2024,,,iDEAL Deposit,,2000.00,EUR,2000.00,EUR,
05-04-2024,08:00,05-04-2024,APPLE INC,US0378331005,Dividend,1.0850,2.17,USD,1500.00,EUR,
05-04-2024,08:00,05-04-2024,APPLE INC,US0378331005,Dividend Tax,1.0850,-0.33,USD,1499.67,EUR,
10-05-2024,09:00,10-05-2024,,,DEGIRO Connectivity Fee 2024,,-2.50,EUR,1497.17,EUR,
02-01-2024,09:30,02-01-2024,APPLE INC,US0378331005,Buy 10 APPLE INC@150 USD,,-1380.00,EUR,620.00,EUR,ord-0001
"""

T212_HISTORY = """Action,Time,ISIN,Ticker,Name,No. of shares,Price / share,Currency (Price / share),Exchange rate,Result,Currency (Result),Total,Currency (Total),Withholding tax,Currency (Withholding tax),Charge amount,Currency (Charge amount),Notes,ID
Deposit,2024-01-02 08:00:00,,,,,,,,,,"1,000.00",EUR,,,,,Bank transfer,dep-1
Market buy,2024-01-05 14:30:02,US0378331005,AAPL,Apple Inc,5.0000000,180.00,USD,1.0900,,,826.19,EUR,,,0.50,EUR,,buy-1
Market sell,2024-06-05 15:00:00,US0378331005,AAPL,Apple Inc,2.0000000,200.00,USD,1.0800,29.63,EUR,369.80,EUR,,,0.50,EUR,,sell-1
Dividend (Ordinary),2024-05-10 12:00:00,US0378331005,AAPL,Apple Inc,5.0000000,0.24,USD,,,,1.10,EUR,0.18,USD,,,,div-1
Interest on cash,2024-07-01 00:00:00,,,,,,,,,,0.42,EUR,,,,,,int-1
"""

# Real-world export (Jan 2025): date column is "Time (UTC)" with a +00:00
# offset, Notes/ID sit before "No. of shares", fee column is "Currency
# conversion fee". This exact shape previously imported as zero rows.
T212_UTC_HEADER = (
    "Action,Time (UTC),ISIN,Ticker,Name,Notes,ID,No. of shares,Price / share,"
    "Currency (Price / share),Exchange rate,Result,Currency (Result),Total,"
    "Currency (Total),Withholding tax,Currency (Withholding tax),"
    "Currency conversion fee,Currency (Currency conversion fee),"
    "French transaction tax,Currency (French transaction tax)\n"
    "Deposit,2025-01-29 17:37:08+00:00,,,,Transaction ID: LX39,dep-1,,,,,,,100,EUR,,,,,,\n"
    "Deposit,2025-01-29 17:37:09+00:00,,,,Free Shares Promotion,dep-2,,,,,,,8.94,EUR,,,,,,\n"
    "Market buy,2025-02-03 14:30:02+00:00,US0378331005,AAPL,Apple Inc,,buy-1,"
    "5.0000000,180.00,USD,1.0900,,,826.19,EUR,,,0.50,EUR,,\n"
    "Market sell,2025-06-05 15:00:00+00:00,US0378331005,AAPL,Apple Inc,,sell-1,"
    "2.0000000,200.00,USD,1.0800,29.63,EUR,369.80,EUR,,,0.50,EUR,,\n"
    "Dividend (Ordinary),2025-05-10 12:00:00+00:00,US0378331005,AAPL,Apple Inc,,"
    "div-1,5.0000000,0.24,USD,,,,1.10,EUR,0.18,USD,,,,\n"
)


def test_parse_number_locales():
    assert _parse_number("1,234.56") == 1234.56
    assert _parse_number("1.234,56") == 1234.56
    assert _parse_number("1234,56") == 1234.56
    assert _parse_number("-1500.00") == -1500.0
    assert _parse_number("") is None
    assert _parse_number(None) is None


def test_detect_format():
    assert detect_format(DEGIRO_TRANSACTIONS) == ("degiro", "transactions")
    assert detect_format(DEGIRO_ACCOUNT) == ("degiro", "account")
    assert detect_format(T212_HISTORY) == ("trading212", "history")
    assert detect_format("foo,bar\n1,2\n") is None


def test_detect_and_parse_semicolon_and_tab_delimited():
    # Degiro exports with commas in some regions and semicolons in others
    # (comma is the EU decimal separator); pasted files may be tab-separated.
    semi = (
        "Date;Time;Value date;Product;ISIN;Description;FX;Change;;Balance;;Order Id\n"
        "01-04-2024;08:10;01-04-2024;APPLE INC;US0378331005;Dividend;;2,88;EUR;2500,00;EUR;\n"
    )
    assert detect_format(semi) == ("degiro", "account")
    rows, _ = parse_degiro_account(semi, "EUR")
    assert len(rows) == 1
    assert rows[0].type == "dividend"
    assert abs(rows[0].amount - 2.88) < 1e-6

    tab = (
        "Date\tTime\tProduct\tISIN\tExchange\tVenue\tQuantity\tPrice\t\tLocal value"
        "\t\tValue\t\tExchange rate\tTransaction and/or third party fees\t\tTotal\t\tOrder ID\n"
        "02-01-2024\t09:30\tAPPLE INC\tUS0378331005\tNDQ\tXNAS\t10\t150,00\tUSD"
        "\t-1500,00\tUSD\t-1380,00\tEUR\t1,0870\t-2,00\tEUR\t-1382,00\tEUR\tord-1\n"
    )
    assert detect_format(tab) == ("degiro", "transactions")
    trows, _ = parse_degiro_transactions(tab, "EUR")
    assert len(trows) == 1
    assert trows[0].type == "buy"
    assert trows[0].shares == 10
    assert abs(trows[0].amount + 1380.0) < 1e-6
    assert abs(trows[0].fees - 2.0) < 1e-6


def test_parse_flatexdegiro_account_currency_first():
    # flatexDEGIRO variant: the "Change"/"Balance" columns hold the CURRENCY and
    # the amount sits in the following unnamed column (reverse of classic).
    text = (
        "Date,Time,Value date,Product,ISIN,Description,FX,Change,,Balance,,Order Id\n"
        '05-07-2026,11:10,30-06-2026,,,Flatex Interest Income,,EUR,"0,00",EUR,"117,60",\n'
        '02-07-2026,11:04,30-06-2026,,,Connectivity Fee DEGIRO 2026,,EUR,"-0,02",EUR,"117,60",\n'
        '01-04-2026,08:10,01-04-2026,APPLE INC,US0378331005,Dividend,,EUR,"12,50",EUR,"130,10",\n'
    )
    assert detect_format(text) == ("degiro", "account")
    rows, _ = parse_degiro_account(text, "EUR")
    by_type = {r.type: r for r in rows}
    # zero-amount interest is skipped; fee and dividend are captured
    assert "fee" in by_type and abs(by_type["fee"].amount + 0.02) < 1e-6
    assert "dividend" in by_type
    assert abs(by_type["dividend"].amount - 12.50) < 1e-6
    assert by_type["dividend"].isin == "US0378331005"


def test_detect_account_across_locales():
    # Degiro account statements are identified by the running Balance/Saldo
    # column, which is stable across export languages.
    en = "Date,Time,Value date,Product,ISIN,Description,FX,Change,,Balance,,Order Id\n"
    nl = "Datum,Tijd,Valutadatum,Product,ISIN,Omschrijving,FX,Mutatie,,Saldo,,Order Id\n"
    pt = "Data,Hora,Data Valor,Produto,ISIN,Descrição,Câmbio,,Variação,,Saldo,,ID da Ordem\n"
    es = "Fecha,Hora,Fecha valor,Producto,ISIN,Descripción,,Variación,,Saldo,,ID de la orden\n"
    for text in (en, nl, pt, es):
        assert detect_format(text) == ("degiro", "account")


def test_parse_degiro_transactions():
    rows, warnings = parse_degiro_transactions(DEGIRO_TRANSACTIONS, "EUR")
    assert len(rows) == 3
    buy = rows[0]
    assert buy.type == "buy"
    assert buy.isin == "US0378331005"
    assert buy.shares == 10
    assert buy.amount == -1380.0
    assert buy.fees == 2.0
    assert buy.price == 150.0
    assert buy.currency == "USD"
    assert buy.external_id == "ord-0001"
    assert buy.date == datetime(2024, 1, 2, 9, 30)

    sell = rows[1]
    assert sell.type == "sell"
    assert sell.shares == 4
    assert sell.amount == 630.0

    asml = rows[2]
    assert asml.type == "buy"
    assert asml.currency == "EUR"
    assert asml.amount == -1200.0


def test_parse_degiro_account():
    rows, warnings = parse_degiro_account(DEGIRO_ACCOUNT, "EUR")
    types = [r.type for r in rows]
    assert types == ["deposit", "dividend", "tax", "fee"]

    deposit = rows[0]
    assert deposit.amount == 2000.0

    dividend = rows[1]
    # USD 2.17 converted via FX 1.0850 -> EUR 2.00
    assert abs(dividend.amount - 2.0) < 0.01
    assert dividend.isin == "US0378331005"

    # Buy row must be skipped (comes from Transactions.csv)
    assert any("Transactions.csv" in w for w in warnings)


def test_parse_trading212():
    rows, warnings = parse_trading212(T212_HISTORY, "EUR")
    by_type = {r.type: r for r in rows}
    assert set(by_type) == {"deposit", "buy", "sell", "dividend", "interest"}

    buy = by_type["buy"]
    assert buy.ticker == "AAPL"
    assert buy.shares == 5
    # Total 826.19 includes the 0.50 fee -> amount excl fees
    assert abs(buy.amount + 825.69) < 1e-6
    assert buy.fees == 0.5

    sell = by_type["sell"]
    assert abs(sell.amount - 370.30) < 1e-6
    assert sell.fees == 0.5

    dividend = by_type["dividend"]
    assert abs(dividend.amount - 1.10) < 1e-6
    assert "withholding" in (dividend.note or "")

    deposit = by_type["deposit"]
    assert deposit.amount == 1000.0


def test_parse_trading212_time_utc_header():
    # Regression: "Time (UTC)" + a +00:00 offset used to skip every row silently.
    assert detect_format(T212_UTC_HEADER) == ("trading212", "history")
    rows, warnings = parse_trading212(T212_UTC_HEADER, "EUR")
    by_type = {}
    for r in rows:
        by_type.setdefault(r.type, []).append(r)

    assert [round(d.amount, 2) for d in by_type["deposit"]] == [100.0, 8.94]
    buy = by_type["buy"][0]
    assert buy.ticker == "AAPL" and buy.shares == 5
    assert abs(buy.amount + 825.69) < 1e-6 and buy.fees == 0.5
    assert buy.date == datetime(2025, 2, 3, 14, 30, 2)
    assert by_type["sell"][0].shares == 2
    assert abs(by_type["dividend"][0].amount - 1.10) < 1e-6
    assert warnings == []


def test_parse_trading212_number_of_shares_variant():
    text = T212_UTC_HEADER.replace("No. of shares", "Number of shares")
    assert detect_format(text) == ("trading212", "history")
    rows, _ = parse_trading212(text, "EUR")
    assert next(r for r in rows if r.type == "buy").shares == 5


def test_parse_trading212_unreadable_date_warns_instead_of_silent_zero():
    text = T212_UTC_HEADER.replace("2025-02-03 14:30:02+00:00", "03.02.2025")
    rows, warnings = parse_trading212(text, "EUR")
    # the deposits/sell/dividend still parse; only the mangled row is dropped
    assert any(r.type == "buy" for r in rows) is False
    assert any("03.02.2025" in w for w in warnings)


def test_money_pair_handles_both_column_orderings():
    # classic Degiro: amount then currency
    assert _money_pair(["x", "-1380,00", "EUR", "y"], 1) == (-1380.0, "EUR")
    # flatexDEGIRO: currency then amount
    assert _money_pair(["x", "EUR", "-1380,00", "y"], 1) == (-1380.0, "EUR")
    # amount with no currency cell
    assert _money_pair(["x", "42,50", "", "y"], 1) == (42.5, None)
    # zero amount is a real value, not "missing"
    assert _money_pair(['x', '0,00', 'EUR'], 1) == (0.0, "EUR")
    # nothing usable
    assert _money_pair(["x", "", ""], 1) == (None, None)
    # no column
    assert _money_pair(["x"], None) == (None, None)


def test_sniff_delimiter_picks_the_real_separator():
    assert _sniff_delimiter("a,b,c,d\n1,2,3,4\n") == ","
    assert _sniff_delimiter("a;b;c;d\n1;2;3;4\n") == ";"
    assert _sniff_delimiter("a\tb\tc\n1\t2\t3\n") == "\t"
    # a genuine single-column file has no separator: fall back to comma, don't
    # invent one that would split values apart.
    assert _sniff_delimiter("Ticker\nAAPL\nMSFT\n") == ","


def test_parse_trading212_semicolon_delimited():
    semi = (
        "Action;Time;ISIN;Ticker;Name;No. of shares;Price / share;"
        "Currency (Price / share);Exchange rate;Result;Currency (Result);Total;"
        "Currency (Total);Withholding tax;Currency (Withholding tax);"
        "Charge amount;Currency (Charge amount);Notes;ID\n"
        "Market buy;2024-01-05 14:30:02;US0378331005;AAPL;Apple Inc;5.0000000;"
        "180.00;USD;1.0900;;;826.19;EUR;;;0.50;EUR;;buy-1\n"
    )
    assert detect_format(semi) == ("trading212", "history")
    rows, _ = parse_trading212(semi, "EUR")
    buy = next(r for r in rows if r.type == "buy")
    assert buy.ticker == "AAPL"
    assert buy.shares == 5
    assert abs(buy.amount + 825.69) < 1e-6
    assert buy.fees == 0.5


def test_flag_duplicates_matches_one_for_one(db_session):
    from datetime import datetime

    from app.models.portfolio import Portfolio, Transaction
    from app.schemas.portfolio import ImportRow
    from app.services.importers import ImportService

    p = Portfolio(user_id=1, name="P", broker="degiro", base_currency="EUR")
    db_session.add(p)
    db_session.flush()
    db_session.add(
        Transaction(
            portfolio_id=p.id, type="buy", date=datetime(2024, 1, 2),
            ticker="AAPL", shares=1, price=100.0, amount=-100.0,
        )
    )
    db_session.commit()

    rows = [
        ImportRow(type="buy", date=datetime(2024, 1, 2), ticker="AAPL",
                  shares=1, price=100.0, amount=-100.0),
        ImportRow(type="buy", date=datetime(2024, 1, 2), ticker="AAPL",
                  shares=1, price=100.0, amount=-100.0),
    ]
    dupes = ImportService(db_session)._flag_duplicates(p, rows)
    assert dupes == 1
    assert [r.duplicate for r in rows] == [True, False]


def test_isin_heuristic_suffixes():
    assert IsinResolver._heuristic("US0378331005", "AAPL", "USD") == "AAPL"
    assert IsinResolver._heuristic("DE0005190003", "BMW", "EUR") == "BMW.DE"
    assert IsinResolver._heuristic("GB00BH4HKS39", "VOD", "GBX") == "VOD.L"
    assert IsinResolver._heuristic("IE00B4L5Y983", "IWDA", "EUR") == "IWDA"
    assert IsinResolver._heuristic("NL0010273215", "ASML", "EUR") == "ASML.AS"
    assert IsinResolver._heuristic("US0378331005", None, "USD") is None
