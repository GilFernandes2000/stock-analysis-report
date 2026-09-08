from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta

import yfinance as yf
from sqlalchemy.orm import Session

from app.config import settings
from app.models.cache import ApiCache
from app.utils.time import utcnow

# Yahoo minor-unit currency codes → (major ISO, divisor)
MINOR_UNITS: dict[str, tuple[str, int]] = {
    "GBp": ("GBP", 100),
    "GBX": ("GBP", 100),
    "ILA": ("ILS", 100),
    "ZAc": ("ZAR", 100),
}

FX_CACHE_TTL_SECONDS = 3600


@dataclass
class NormalizedMoney:
    amount: float
    currency: str
    raw_currency: str | None = None
    was_minor_unit: bool = False


def minor_unit_divisor(raw_currency: str | None) -> int:
    if raw_currency and raw_currency.strip() in MINOR_UNITS:
        return MINOR_UNITS[raw_currency.strip()][1]
    return 1


def normalize_to_major(price: float, raw_currency: str | None) -> NormalizedMoney:
    if raw_currency is None:
        return NormalizedMoney(amount=price, currency="USD", raw_currency=None)

    raw = raw_currency.strip()
    if raw in MINOR_UNITS:
        major, divisor = MINOR_UNITS[raw]
        return NormalizedMoney(
            amount=round(price / divisor, 4),
            currency=major,
            raw_currency=raw,
            was_minor_unit=True,
        )

    return NormalizedMoney(
        amount=price,
        currency=raw.upper(),
        raw_currency=raw,
        was_minor_unit=False,
    )


def currency_note(normalized: NormalizedMoney) -> str | None:
    if not normalized.was_minor_unit:
        return None
    symbol = {"GBP": "£", "EUR": "€", "USD": "$", "ILS": "₪", "ZAR": "R"}.get(
        normalized.currency, normalized.currency
    )
    return (
        f"Quoted in {normalized.raw_currency} (minor units); "
        f"native {symbol}{normalized.amount:.2f}"
    )


class CurrencyService:
    def __init__(self, db: Session):
        self.db = db

    def validate_display_currency(self, code: str) -> str:
        upper = code.upper()
        if upper not in settings.supported_display_currencies:
            raise ValueError(
                f"Unsupported currency {code}. "
                f"Supported: {', '.join(settings.supported_display_currencies)}"
            )
        return upper

    def get_fx_rate(self, from_iso: str, to_iso: str) -> float:
        from_iso = from_iso.upper()
        to_iso = to_iso.upper()
        if from_iso == to_iso:
            return 1.0

        cache_key = f"fx:{from_iso}:{to_iso}"
        row = self.db.query(ApiCache).filter(ApiCache.cache_key == cache_key).first()
        if row:
            age = utcnow() - row.created_at
            if age <= timedelta(seconds=FX_CACHE_TTL_SECONDS):
                return float(json.loads(row.payload))

        rate = self._fetch_fx_rate(from_iso, to_iso)

        payload = json.dumps(rate)
        if row:
            row.payload = payload
            row.created_at = utcnow()
        else:
            self.db.add(ApiCache(cache_key=cache_key, payload=payload))
        self.db.commit()
        return rate

    @staticmethod
    def _fetch_fx_rate(from_iso: str, to_iso: str) -> float:
        pair = f"{from_iso}{to_iso}=X"
        ticker = yf.Ticker(pair)
        price = ticker.info.get("regularMarketPrice") or ticker.info.get("regularMarketPreviousClose")
        if price:
            return float(price)

        inverse_pair = f"{to_iso}{from_iso}=X"
        inv = yf.Ticker(inverse_pair)
        inv_price = inv.info.get("regularMarketPrice") or inv.info.get(
            "regularMarketPreviousClose"
        )
        if inv_price and float(inv_price) != 0:
            return 1.0 / float(inv_price)

        raise ValueError(f"Could not fetch FX rate for {from_iso} → {to_iso}")

    def convert(
        self, amount: float | None, from_iso: str, to_iso: str
    ) -> float | None:
        if amount is None:
            return None
        rate = self.get_fx_rate(from_iso, to_iso)
        return round(amount * rate, 4)

    def normalize_and_convert(
        self,
        price: float | None,
        raw_currency: str | None,
        display_currency: str,
        *,
        finviz_default: bool = False,
    ) -> tuple[float | None, str, float | None, str | None]:
        """Returns display_price, native_currency, native_price, note."""
        if price is None:
            return None, display_currency, None, None

        raw = "USD" if finviz_default and not raw_currency else raw_currency
        normalized = normalize_to_major(price, raw)
        display = self.convert(normalized.amount, normalized.currency, display_currency)
        note = currency_note(normalized)
        return display, normalized.currency, normalized.amount, note
