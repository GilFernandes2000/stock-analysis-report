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


def _cell(row: list[str], idx: int | None) -> str | None:
    if idx is None or idx >= len(row):
        return None
    return row[idx]


def parse_degiro_transactions(
    text: str, base_currency: str
) -> tuple[list[ImportRow], list[str]]:
    reader = csv.reader(io.StringIO(text))
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
        value = _parse_number(_cell(line, idx["value"])) or 0.0
        value_ccy = _currency_after(headers, line, idx["value"]) or base_currency
        price = _parse_number(_cell(line, idx["price"]))
        price_ccy = _currency_after(headers, line, idx["price"])
        fee = abs(_parse_number(_cell(line, idx["fee"])) or 0.0)
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
    reader = csv.reader(io.StringIO(text))
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
        change = _parse_number(_cell(line, idx["change"]))
        if date is None or change is None or change == 0 or not desc:
            continue
        desc_lower = desc.lower()
        change_ccy = _currency_after(headers, line, idx["change"]) or base_currency
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


def _t212_date(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def parse_trading212(text: str, base_currency: str) -> tuple[list[ImportRow], list[str]]:
    reader = csv.DictReader(io.StringIO(text))
    rows: list[ImportRow] = []
    warnings: list[str] = []
    skipped_actions: set[str] = set()
    mismatched_currency = False

    for record in reader:
        rec = {_norm_header(k or ""): (v or "").strip() for k, v in record.items()}
        action = rec.get("action", "").lower()
        date = _t212_date(rec.get("time", ""))
        if not action or date is None:
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
        shares = _parse_number(rec.get("no. of shares"))
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
            skipped_actions.add(rec.get("action", action))

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
        if row and datetime.utcnow() - row.created_at <= ISIN_CACHE_TTL:
            cached = json.loads(row.payload)
            return cached or None

        symbol = self._lookup(isin, currency) or self._heuristic(
            isin, fallback_ticker, currency
        )

        payload = json.dumps(symbol or "")
        if row:
            row.payload = payload
            row.created_at = datetime.utcnow()
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
                    from app.services.portfolio_analytics import _major, _suffix_currency

                    wanted = _major(currency)
                    for quote in quotes:
                        if _major(_suffix_currency(quote["symbol"])) == wanted:
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


def detect_format(text: str) -> tuple[str, str] | None:
    """Return (broker, file_kind) or None."""
    first_line = text.split("\n", 1)[0]
    headers = [_norm_header(h) for h in next(csv.reader(io.StringIO(first_line)), [])]
    header_set = set(headers)

    if "action" in header_set and any("no. of shares" in h for h in headers):
        return "trading212", "history"
    has_isin = "isin" in header_set
    if has_isin and _find_column(headers, _DG_QTY) is not None and _find_column(headers, _DG_ORDER_ID) is not None:
        return "degiro", "transactions"
    if has_isin and _find_column(headers, _DG_DESCRIPTION) is not None and _find_column(headers, _DG_CHANGE) is not None:
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
            return ImportPreviewResponse(
                broker="unknown",
                file_kind="unknown",
                rows=[],
                total_rows=0,
                duplicate_count=0,
                unresolved_isins=[],
                warnings=[
                    f"Could not recognize '{filename}'. Expected a Degiro "
                    "Transactions/Account export or a Trading 212 history CSV."
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
