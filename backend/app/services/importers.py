"""Broker CSV import: Degiro (Transactions + Account statement) and Trading 212.

Flow: preview(file) -> parsed ImportRows with duplicate/resolution flags,
user reviews/edits -> commit(rows) persists Transactions.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
from datetime import datetime, timedelta

import yfinance as yf
from sqlalchemy.orm import Session

from app.models.cache import ApiCache
from app.models.portfolio import (
    TRANSACTION_TYPES,
    TXN_BUY,
    TXN_DEPOSIT,
    TXN_DIVIDEND,
    TXN_FEE,
    TXN_INTEREST,
    TXN_SELL,
    TXN_TAX,
    TXN_WITHDRAWAL,
    Portfolio,
    Transaction,
)
from app.schemas.portfolio import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportPreviewResponse,
    ImportRow,
)
from app.utils.time import utcnow

logger = logging.getLogger(__name__)

ISIN_CACHE_TTL = timedelta(days=30)

# ISIN country prefix -> Yahoo exchange suffix (heuristic fallback)
ISIN_SUFFIX_BY_COUNTRY: dict[str, str] = {
    "US": "",
    "GB": ".L",
    "IE": ".L",  # Irish-domiciled ETFs usually trade on LSE
    "DE": ".DE",
    "NL": ".AS",
    "FR": ".PA",
    "PT": ".LS",
    "ES": ".MC",
    "IT": ".MI",
    "CH": ".SW",
    "BE": ".BR",
    "AT": ".VI",
    "DK": ".CO",
    "FI": ".HE",
    "SE": ".ST",
    "NO": ".OL",
    "CA": ".TO",
    "AU": ".AX",
}


def _parse_number(raw: str | None) -> float | None:
    """Parse localized numbers: '1,234.56', '1.234,56', '1234,56', '-1 234,56'."""
    if raw is None:
        return None
    text = raw.strip().replace(" ", "").replace(" ", "")
    if not text or text in ("-", "--"):
        return None
    negative = text.startswith("-") or (text.startswith("(") and text.endswith(")"))
    text = text.strip("()-+")
    if "," in text and "." in text:
        # Whichever separator comes last is the decimal separator
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        # Treat a single comma group as decimal separator (Degiro EU locales)
        if text.count(",") == 1:
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")
    try:
        value = float(text)
    except ValueError:
        return None
    return -value if negative else value


def _synth_id(*parts: object) -> str:
    digest = hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()
    return f"synth-{digest[:20]}"


def _norm_header(value: str) -> str:
    return value.strip().lower().replace("﻿", "")


def _find_column(headers: list[str], synonyms: tuple[str, ...]) -> int | None:
    normed = [_norm_header(h) for h in headers]
    for syn in synonyms:
        if syn in normed:
            return normed.index(syn)
    return None


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


_CANDIDATE_DELIMITERS = (",", ";", "\t", "|")


def _split_header(text: str, delimiter: str) -> list[str]:
    first_line = text.split("\n", 1)[0]
    row = next(csv.reader(io.StringIO(first_line), delimiter=delimiter), [])
    return [_norm_header(h) for h in row]


def _sniff_delimiter(text: str) -> str:
    """Pick the delimiter that actually splits the header into the most columns.

    Broker exports vary by region: Degiro uses commas in some locales and
    semicolons in others (comma is the decimal separator in much of Europe),
    and pasted/re-saved files can end up tab-separated. The wrong delimiter
    yields a single unsplit column, so 'most columns wins' is unambiguous.
    """
    best_delim, best_cols = ",", 0
    for delimiter in _CANDIDATE_DELIMITERS:
        cols = len(_split_header(text, delimiter))
        if cols > best_cols:
            best_delim, best_cols = delimiter, cols
    return best_delim


def _reader(text: str):
    return csv.reader(io.StringIO(text), delimiter=_sniff_delimiter(text))


# ---------------------------------------------------------------------------
# Degiro
# ---------------------------------------------------------------------------

_DG_DATE = ("date", "datum", "data")
_DG_TIME = ("time", "tijd", "hora")
_DG_PRODUCT = ("product", "produto", "producto", "prodotto")
_DG_ISIN = ("isin",)
_DG_QTY = ("quantity", "aantal", "quantidade", "cantidad", "quantità")
_DG_PRICE = ("price", "koers", "cotação", "cotacao", "precio", "prezzo", "preço")
_DG_LOCAL_VALUE = ("local value", "lokale waarde", "valor local", "valore locale")
_DG_VALUE = ("value", "waarde", "valor", "valore")
_DG_FX = ("exchange rate", "wisselkoers", "taxa de câmbio", "taxa de cambio", "tipo de cambio", "tasso di cambio")
_DG_FEE = (
    "transaction and/or third party fees",
    "transaction costs",
    "transactiekosten en/of kosten van derden",
    "transactiekosten",
    "custos de transação e/ou de terceiros",
    "custos de transação",
    "costes de transacción",
    "costi di transazione",
)
_DG_TOTAL = ("total", "totaal", "totale")
_DG_ORDER_ID = ("order id", "order-id", "id da ordem", "id de la orden", "id ordine")
_DG_DESCRIPTION = ("description", "omschrijving", "descrição", "descricao", "descripción", "descrizione")
_DG_CHANGE = ("change", "mutatie", "variação", "variacao", "variación", "variazione", "mutação")
_DG_BALANCE = ("balance", "saldo")


def _degiro_date(date_str: str, time_str: str | None) -> datetime | None:
    date_str = (date_str or "").strip()
    time_str = (time_str or "").strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            base = datetime.strptime(date_str, fmt)
        except ValueError:
            continue
        if time_str:
            try:
                t = datetime.strptime(time_str, "%H:%M")
                return base.replace(hour=t.hour, minute=t.minute)
            except ValueError:
                pass
        return base
    return None


def _currency_after(headers: list[str], row: list[str], idx: int | None) -> str | None:
    """Degiro money columns are followed by an unnamed currency column."""
    if idx is None or idx + 1 >= len(row):
        return None
    if _norm_header(headers[idx + 1]) == "" or "unnamed" in _norm_header(headers[idx + 1]):
        code = row[idx + 1].strip().upper()
        return code or None
    return None


_CCY_RE = re.compile(r"^[A-Za-z]{3}$")


def _money_pair(row: list[str], idx: int | None) -> tuple[float | None, str | None]:
    """Extract (amount, currency) from a Degiro money value.

    Degiro splits each money value across two adjacent columns — an amount and
    a 3-letter currency code — but their order varies by export: classic
    exports put the amount first and currency second, while flatexDEGIRO puts
    the currency first and amount second. Scan both cells and assign by type so
    either ordering works.
    """
    if idx is None:
        return None, None
    amount: float | None = None
    currency: str | None = None
    for cell in (_cell(row, idx), _cell(row, idx + 1)):
        if not cell or not cell.strip():
            continue
        text = cell.strip()
        num = _parse_number(text)
        if num is not None and amount is None:
            amount = num
        elif _CCY_RE.match(text) and currency is None:
            currency = text.upper()
    return amount, currency


def _cell(row: list[str], idx: int | None) -> str | None:
    if idx is None or idx >= len(row):
        return None
    return row[idx]


def parse_degiro_transactions(
    text: str, base_currency: str
) -> tuple[list[ImportRow], list[str]]:
    reader = _reader(text)
    table = [r for r in reader if any(cell.strip() for cell in r)]
    if not table:
        return [], ["File is empty"]
    headers = table[0]
    idx = {
        "date": _find_column(headers, _DG_DATE),
        "time": _find_column(headers, _DG_TIME),
        "product": _find_column(headers, _DG_PRODUCT),
        "isin": _find_column(headers, _DG_ISIN),
        "qty": _find_column(headers, _DG_QTY),
        "price": _find_column(headers, _DG_PRICE),
        "value": _find_column(headers, _DG_VALUE),
        "fx": _find_column(headers, _DG_FX),
        "fee": _find_column(headers, _DG_FEE),
        "order": _find_column(headers, _DG_ORDER_ID),
    }
    # "Value" synonyms also match "Local value"; prefer the later occurrence
    local_idx = _find_column(headers, _DG_LOCAL_VALUE)
    if idx["value"] is not None and idx["value"] == local_idx:
        normed = [_norm_header(h) for h in headers]
        for i in range(len(headers) - 1, -1, -1):
            if normed[i] in _DG_VALUE and i != local_idx:
                idx["value"] = i
                break

    rows: list[ImportRow] = []
    warnings: list[str] = []
    mismatched_currency = False

    for line in table[1:]:
        date = _degiro_date(_cell(line, idx["date"]) or "", _cell(line, idx["time"]))
        qty = _parse_number(_cell(line, idx["qty"]))
        if date is None or qty is None or qty == 0:
            continue
        # Money values span an amount + currency pair in adjacent columns whose
        # order varies by export variant (classic vs flatexDEGIRO).
        value, value_ccy = _money_pair(line, idx["value"])
        value = value or 0.0
        value_ccy = value_ccy or base_currency
        price, price_ccy = _money_pair(line, idx["price"])
        fee_amt, _ = _money_pair(line, idx["fee"])
        fee = abs(fee_amt or 0.0)
        fx = _parse_number(_cell(line, idx["fx"]))
        isin = (_cell(line, idx["isin"]) or "").strip().upper() or None
        product = (_cell(line, idx["product"]) or "").strip() or None
        order_id = (_cell(line, idx["order"]) or "").strip() or None

        if value_ccy != base_currency:
            mismatched_currency = True

        txn_type = TXN_BUY if qty > 0 else TXN_SELL
        rows.append(
            ImportRow(
                type=txn_type,
                date=date,
                isin=isin,
                name=product,
                shares=abs(qty),
                price=price,
                currency=price_ccy,
                amount=value,  # signed: buy negative, sell positive
                fees=fee,
                fx_rate=fx,
                external_id=order_id or _synth_id(date, isin, qty, value),
                ticker=None,
                ticker_resolved=False,
            )
        )

    if mismatched_currency:
        warnings.append(
            f"Some rows settle in a currency different from the portfolio base "
            f"currency ({base_currency}); Degiro's converted 'Value' column was used."
        )
    return rows, warnings


_DG_SKIP_KEYWORDS = (
    "fx credit",
    "fx debit",
    "valuta creditering",
    "valuta debitering",
    "money market fund",
    "fundo do mercado monetário",
    "geldmarktfonds",
    "conversão de fundo",
    "cash sweep",
    "compensação",
)
_DG_TRADE_KEYWORDS = ("buy", "sell", "koop", "verkoop", "compra", "venda", "comprar", "vender")
_DG_DIV_TAX_KEYWORDS = ("dividendbelasting", "dividend tax", "imposto sobre dividendo", "retención")
_DG_DIVIDEND_KEYWORDS = ("dividend", "dividendo")
_DG_DEPOSIT_KEYWORDS = ("deposit", "storting", "depósito", "deposito", "ingreso")
_DG_WITHDRAW_KEYWORDS = ("withdrawal", "opname", "levantamento", "terugstorting", "retirada")
_DG_INTEREST_KEYWORDS = ("interest", "rente", "juro", "juros", "interés")
_DG_TXN_FEE_KEYWORDS = (
    "transaction and/or third party",
    "transactiekosten",
    "custos de transação",
    "costes de transacción",
)
_DG_FEE_KEYWORDS = (
    "fee",
    "kosten",
    "custo",
    "comissão",
    "comissoes",
    "comisión",
    "conectividade",
    "connectivity",
    "aansluitkosten",
)


def parse_degiro_account(
    text: str, base_currency: str
) -> tuple[list[ImportRow], list[str]]:
    reader = _reader(text)
    table = [r for r in reader if any(cell.strip() for cell in r)]
    if not table:
        return [], ["File is empty"]
    headers = table[0]
    idx = {
        "date": _find_column(headers, _DG_DATE),
        "time": _find_column(headers, _DG_TIME),
        "product": _find_column(headers, _DG_PRODUCT),
        "isin": _find_column(headers, _DG_ISIN),
        "desc": _find_column(headers, _DG_DESCRIPTION),
        "fx": _find_column(headers, ("fx",) + _DG_FX),
        "change": _find_column(headers, _DG_CHANGE),
        "order": _find_column(headers, _DG_ORDER_ID),
    }

    rows: list[ImportRow] = []
    warnings: list[str] = []
    skipped_trades = 0

    for line in table[1:]:
        date = _degiro_date(_cell(line, idx["date"]) or "", _cell(line, idx["time"]))
        desc = (_cell(line, idx["desc"]) or "").strip()
        # The amount and its currency occupy the "Change" column and the unnamed
        # column next to it, in either order depending on the export variant.
        change, change_ccy = _money_pair(line, idx["change"])
        if date is None or change is None or change == 0 or not desc:
            continue
        desc_lower = desc.lower()
        change_ccy = change_ccy or base_currency
        isin = (_cell(line, idx["isin"]) or "").strip().upper() or None
        product = (_cell(line, idx["product"]) or "").strip() or None
        fx = _parse_number(_cell(line, idx["fx"]))
        order_id = (_cell(line, idx["order"]) or "").strip() or None

        if any(k in desc_lower for k in _DG_SKIP_KEYWORDS):
            continue
        if any(k in desc_lower for k in _DG_TRADE_KEYWORDS) and isin:
            skipped_trades += 1  # trades come from Transactions.csv
            continue
        if any(k in desc_lower for k in _DG_TXN_FEE_KEYWORDS):
            continue  # already captured as fees in Transactions.csv

        if any(k in desc_lower for k in _DG_DIV_TAX_KEYWORDS):
            txn_type = TXN_TAX
        elif any(k in desc_lower for k in _DG_DIVIDEND_KEYWORDS):
            txn_type = TXN_DIVIDEND
        elif any(k in desc_lower for k in _DG_DEPOSIT_KEYWORDS):
            txn_type = TXN_DEPOSIT
        elif any(k in desc_lower for k in _DG_WITHDRAW_KEYWORDS):
            txn_type = TXN_WITHDRAWAL
        elif any(k in desc_lower for k in _DG_INTEREST_KEYWORDS):
            txn_type = TXN_INTEREST
        elif any(k in desc_lower for k in _DG_FEE_KEYWORDS):
            txn_type = TXN_FEE
        else:
            continue

        amount = change
        if change_ccy != base_currency:
            if fx and fx > 0:
                amount = round(change / fx, 4)
            else:
                warnings.append(
                    f"{date.date()} '{desc}': amount in {change_ccy} without an FX "
                    f"rate; imported unconverted."
                )

        rows.append(
            ImportRow(
                type=txn_type,
                date=date,
                isin=isin if txn_type in (TXN_DIVIDEND, TXN_TAX) else None,
                name=product if txn_type in (TXN_DIVIDEND, TXN_TAX) else None,
                amount=amount,
                currency=change_ccy,
                fx_rate=fx,
                note=desc,
                external_id=order_id or _synth_id(date, desc, isin, change),
                ticker=None,
                ticker_resolved=txn_type not in (TXN_DIVIDEND, TXN_TAX) or isin is None,
            )
        )

    if skipped_trades:
        warnings.append(
            f"Skipped {skipped_trades} buy/sell rows — import the Degiro "
            "Transactions.csv export for trades."
        )
    return rows, warnings


# ---------------------------------------------------------------------------
# Trading 212
# ---------------------------------------------------------------------------

_T212_FEE_COLUMNS = (
    "charge amount",
    "currency conversion fee",
    "stamp duty",
    "stamp duty reserve tax",
    "transaction fee",
    "finra fee",
    "french transaction tax",
    "deposit fee",
)


def _t212_get(rec: dict[str, str], *names: str) -> str:
    """First non-empty value among the given normalized header names.

    Falls back to any key that *starts with* the first name, so a renamed
    column like ``Time (UTC)`` still resolves for ``_t212_get(rec, "time")``.
    """
    for name in names:
        value = rec.get(name)
        if value:
            return value
    prefix = names[0]
    for key, value in rec.items():
        if value and key.startswith(prefix):
            return value
    return ""


_T212_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%d",
    "%d/%m/%Y",
)


def _t212_date(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in _T212_DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=None)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def parse_trading212(text: str, base_currency: str) -> tuple[list[ImportRow], list[str]]:
    reader = csv.DictReader(io.StringIO(text), delimiter=_sniff_delimiter(text))
    rows: list[ImportRow] = []
    warnings: list[str] = []
    skipped_actions: set[str] = set()
    mismatched_currency = False
    no_action = 0
    bad_date = 0
    bad_date_sample = ""

    for record in reader:
        rec = {_norm_header(k or ""): (v or "").strip() for k, v in record.items()}
        action = _t212_get(rec, "action").lower()
        raw_date = _t212_get(rec, "time", "time (utc)")
        date = _t212_date(raw_date)
        if not action:
            no_action += 1
            continue
        if date is None:
            bad_date += 1
            bad_date_sample = bad_date_sample or raw_date
            continue

        total = _parse_number(rec.get("total"))
        total_ccy = (rec.get("currency (total)") or base_currency).upper()
        if total_ccy and total_ccy != base_currency:
            mismatched_currency = True

        fees = 0.0
        for col in _T212_FEE_COLUMNS:
            fees += abs(_parse_number(rec.get(col)) or 0.0)

        ticker = rec.get("ticker") or None
        isin = (rec.get("isin") or "").upper() or None
        name = rec.get("name") or None
        shares = _parse_number(
            _t212_get(rec, "no. of shares", "number of shares", "shares")
        )
        price = _parse_number(rec.get("price / share"))
        price_ccy = (rec.get("currency (price / share)") or "").upper() or None
        fx = _parse_number(rec.get("exchange rate"))
        external_id = rec.get("id") or _synth_id(date, action, ticker, total)
        note = rec.get("notes") or None

        if "buy" in action:
            if total is None:
                continue
            net = abs(total) - fees
            rows.append(
                ImportRow(
                    type=TXN_BUY, date=date, ticker=ticker, isin=isin, name=name,
                    shares=abs(shares or 0), price=price, currency=price_ccy,
                    amount=-net, fees=fees, fx_rate=fx, note=note,
                    external_id=external_id, ticker_resolved=False,
                )
            )
        elif "sell" in action:
            if total is None:
                continue
            rows.append(
                ImportRow(
                    type=TXN_SELL, date=date, ticker=ticker, isin=isin, name=name,
                    shares=abs(shares or 0), price=price, currency=price_ccy,
                    amount=abs(total) + fees, fees=fees, fx_rate=fx, note=note,
                    external_id=external_id, ticker_resolved=False,
                )
            )
        elif "dividend" in action:
            withholding = _parse_number(rec.get("withholding tax"))
            note_parts = [p for p in (note,) if p]
            if withholding:
                note_parts.append(f"withholding tax {withholding:g}")
            rows.append(
                ImportRow(
                    type=TXN_DIVIDEND, date=date, ticker=ticker, isin=isin, name=name,
                    shares=shares, price=price, currency=price_ccy,
                    amount=abs(total or 0.0), fees=0.0, fx_rate=fx,
                    note="; ".join(note_parts) or None,
                    external_id=external_id, ticker_resolved=False,
                )
            )
        elif "deposit" in action:
            rows.append(
                ImportRow(
                    type=TXN_DEPOSIT, date=date, amount=abs(total or 0.0), fees=fees,
                    note=note, external_id=external_id,
                )
            )
        elif "withdraw" in action:
            rows.append(
                ImportRow(
                    type=TXN_WITHDRAWAL, date=date, amount=-abs(total or 0.0),
                    fees=fees, note=note, external_id=external_id,
                )
            )
        elif "interest" in action:
            rows.append(
                ImportRow(
                    type=TXN_INTEREST, date=date, amount=total or 0.0, note=note,
                    external_id=external_id,
                )
            )
        elif "currency conversion" in action:
            continue
        else:
            skipped_actions.add(_t212_get(rec, "action") or action)

    if bad_date:
        warnings.append(
            f"Skipped {bad_date} row(s): couldn't parse the date value "
            f"'{bad_date_sample}'. Report this format so it can be added."
        )
    if no_action and not rows:
        warnings.append(
            f"Skipped {no_action} rows: the Action column was empty — the file "
            "may use an unexpected delimiter or header layout."
        )
    if skipped_actions:
        warnings.append(f"Skipped unsupported actions: {', '.join(sorted(skipped_actions))}")
    if mismatched_currency:
        warnings.append(
            "Some totals are in a different currency than the portfolio base "
            "currency; check that your Trading 212 account currency matches."
        )
    return rows, warnings


# ---------------------------------------------------------------------------
# ISIN -> Yahoo ticker resolution
# ---------------------------------------------------------------------------


class IsinResolver:
    def __init__(self, db: Session):
        self.db = db

    def resolve(
        self,
        isin: str,
        fallback_ticker: str | None = None,
        currency: str | None = None,
    ) -> str | None:
        cache_key = f"isin:{isin}"
        row = self.db.query(ApiCache).filter(ApiCache.cache_key == cache_key).first()
        if row and utcnow() - row.created_at <= ISIN_CACHE_TTL:
            cached = json.loads(row.payload)
            return cached or None

        symbol = self._lookup(isin, currency) or self._heuristic(
            isin, fallback_ticker, currency
        )

        payload = json.dumps(symbol or "")
        if row:
            row.payload = payload
            row.created_at = utcnow()
        else:
            self.db.add(ApiCache(cache_key=cache_key, payload=payload))
        self.db.commit()
        return symbol

    @staticmethod
    def _lookup(isin: str, currency: str | None = None) -> str | None:
        try:
            search = yf.Search(isin, max_results=5)
            quotes = [q for q in (search.quotes or []) if q.get("symbol")]
            if quotes:
                # An ISIN can list on several exchanges (e.g. VUSA on LSE in GBp
                # and on Euronext in EUR); prefer the listing whose currency
                # matches the currency the trade settled in.
                if currency:
                    from app.services.market_math import major_currency, suffix_currency

                    wanted = major_currency(currency)
                    for quote in quotes:
                        if major_currency(suffix_currency(quote["symbol"])) == wanted:
                            return quote["symbol"]
                return quotes[0].get("symbol")
        except Exception as exc:  # network / API shape changes
            logger.debug("ISIN search failed for %s: %s", isin, exc)
        try:
            ticker = yf.utils.get_ticker_by_isin(isin)
            return ticker or None
        except Exception as exc:
            logger.debug("get_ticker_by_isin failed for %s: %s", isin, exc)
        return None

    @staticmethod
    def _heuristic(
        isin: str, fallback_ticker: str | None, currency: str | None
    ) -> str | None:
        if not fallback_ticker:
            return None
        country = isin[:2].upper() if len(isin) >= 2 else ""
        ticker = fallback_ticker.upper()
        if "." in ticker:
            return ticker
        suffix = ISIN_SUFFIX_BY_COUNTRY.get(country)
        if suffix is None:
            return ticker
        if country in ("GB", "IE") and currency not in (None, "GBP", "GBX", "GBp"):
            # Irish/UK ISIN trading in EUR/USD is likely a continental listing
            return ticker
        return f"{ticker}{suffix}"


# ---------------------------------------------------------------------------
# Import orchestration
# ---------------------------------------------------------------------------


def screener_headers(text: str) -> list[str]:
    """The normalized header names of a CSV's first line (for diagnostics)."""
    first_line = text.split("\n", 1)[0]
    return [_norm_header(h) for h in next(_reader(first_line), []) if h]


def detect_format(text: str) -> tuple[str, str] | None:
    """Return (broker, file_kind) or None.

    Detection keys off columns that are stable across Degiro's export
    languages: a *Quantity* column is unique to Transactions.csv, and a running
    *Balance/Saldo* column is unique to the Account statement (Account.csv).
    """
    first_line = text.split("\n", 1)[0]
    headers = [_norm_header(h) for h in next(_reader(first_line), [])]
    header_set = set(headers)

    if "action" in header_set and any(
        s in h for h in headers for s in ("no. of shares", "number of shares")
    ):
        return "trading212", "history"

    has_isin = "isin" in header_set
    has_qty = _find_column(headers, _DG_QTY) is not None
    has_balance = _find_column(headers, _DG_BALANCE) is not None
    has_desc = _find_column(headers, _DG_DESCRIPTION) is not None
    has_change = _find_column(headers, _DG_CHANGE) is not None

    # Transactions.csv — the Quantity column is unique to trade rows.
    if has_isin and has_qty:
        return "degiro", "transactions"
    # Account.csv — the running Balance/Saldo column is unique to the account
    # statement and consistently named across locales (Balance / Saldo).
    if has_balance and (has_isin or has_desc or has_change):
        return "degiro", "account"
    # Lenient fallback: any Degiro-shaped statement (has ISIN, no Quantity)
    # with a description/change/balance column is treated as an account file.
    if has_isin and not has_qty and (has_desc or has_change or has_balance):
        return "degiro", "account"
    return None


class ImportService:
    def __init__(self, db: Session):
        self.db = db
        self.resolver = IsinResolver(db)

    def preview(
        self, portfolio: Portfolio, content: bytes, filename: str
    ) -> ImportPreviewResponse:
        text = _decode(content)
        detected = detect_format(text)
        if detected is None:
            found = screener_headers(text)
            header_hint = ", ".join(found[:12]) if found else "no header row detected"
            return ImportPreviewResponse(
                broker="unknown",
                file_kind="unknown",
                rows=[],
                total_rows=0,
                duplicate_count=0,
                unresolved_isins=[],
                warnings=[
                    f"Could not recognize '{filename}'. Expected a Degiro "
                    "Transactions/Account export or a Trading 212 history CSV.",
                    f"Columns found: {header_hint}.",
                    "For a Degiro account statement the file needs a "
                    "Balance/Saldo column; for trades it needs a Quantity column.",
                ],
            )
        broker, kind = detected
        if broker == "trading212":
            rows, warnings = parse_trading212(text, portfolio.base_currency)
        elif kind == "transactions":
            rows, warnings = parse_degiro_transactions(text, portfolio.base_currency)
        else:
            rows, warnings = parse_degiro_account(text, portfolio.base_currency)

        unresolved = self._resolve_tickers(rows)
        duplicates = self._flag_duplicates(portfolio, rows)

        return ImportPreviewResponse(
            broker=broker,
            file_kind=kind,
            rows=rows,
            total_rows=len(rows),
            duplicate_count=duplicates,
            unresolved_isins=sorted(unresolved),
            warnings=warnings,
        )

    def _resolve_tickers(self, rows: list[ImportRow]) -> set[str]:
        resolved_cache: dict[str, str | None] = {}
        unresolved: set[str] = set()
        for row in rows:
            if row.ticker_resolved:
                continue
            if not row.isin:
                # Trading 212 rows always carry an ISIN; nothing else to do
                row.ticker_resolved = row.ticker is not None
                continue
            if row.isin not in resolved_cache:
                resolved_cache[row.isin] = self.resolver.resolve(
                    row.isin, fallback_ticker=row.ticker, currency=row.currency
                )
            symbol = resolved_cache[row.isin]
            if symbol:
                row.ticker = symbol
                row.ticker_resolved = True
            elif row.ticker:
                row.ticker_resolved = True  # keep broker ticker as best effort
            else:
                unresolved.add(row.isin)
        return unresolved

    def _flag_duplicates(self, portfolio: Portfolio, rows: list[ImportRow]) -> int:
        existing = self.db.query(Transaction).filter(
            Transaction.portfolio_id == portfolio.id
        )
        existing_ids = {t.external_id for t in existing if t.external_id}
        existing_sigs = {
            (t.date.date(), t.type, (t.ticker or t.isin or ""), round(t.amount, 2))
            for t in existing
        }
        count = 0
        for row in rows:
            sig = (
                row.date.date(),
                row.type,
                (row.ticker or row.isin or ""),
                round(row.amount, 2),
            )
            if (row.external_id and row.external_id in existing_ids) or sig in existing_sigs:
                row.duplicate = True
                count += 1
        return count

    def commit(
        self, portfolio: Portfolio, payload: ImportCommitRequest
    ) -> ImportCommitResponse:
        imported = 0
        skipped = 0
        existing_ids = {
            t.external_id
            for t in self.db.query(Transaction).filter(
                Transaction.portfolio_id == portfolio.id
            )
            if t.external_id
        }
        for row in payload.rows:
            if row.type not in TRANSACTION_TYPES:
                skipped += 1
                continue
            if payload.skip_duplicates and (
                row.duplicate or (row.external_id and row.external_id in existing_ids)
            ):
                skipped += 1
                continue
            txn = Transaction(
                portfolio_id=portfolio.id,
                external_id=row.external_id,
                type=row.type,
                date=row.date,
                ticker=row.ticker.upper() if row.ticker else None,
                isin=row.isin,
                name=row.name,
                shares=row.shares,
                price=row.price,
                currency=row.currency,
                amount=row.amount,
                fees=row.fees,
                fx_rate=row.fx_rate,
                note=row.note,
            )
            self.db.add(txn)
            if row.external_id:
                existing_ids.add(row.external_id)
            imported += 1
        self.db.commit()
        return ImportCommitResponse(imported=imported, skipped=skipped)
