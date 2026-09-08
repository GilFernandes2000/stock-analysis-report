import json
import re
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import finviz
from finviz.screener import Screener
from sqlalchemy.orm import Session

from app.config import ALL_SCREENS, settings
from app.models.cache import ApiCache
from app.utils.time import utcnow

_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,6}$")


def _fix_screener_row(row: dict[str, str]) -> dict[str, str]:
    """Realign a Finviz screener row when a ticker-logo column is present.

    Finviz injects a logo cell (a single letter matching the real ticker's
    first character) ahead of the ticker. The pinned ``finviz`` library uses a
    hardcoded header list that doesn't include it, so every value ends up one
    column to the right of its label (ticker "ZTS" lands under "Perf Week",
    price under "Change", etc.). Detect that injected cell and shift the values
    back into alignment. Self-guarding: only shifts when the logo pattern is
    unambiguously present, so it's a no-op if Finviz drops the column again.
    """
    keys = list(row.keys())
    values = list(row.values())
    if "Ticker" not in keys:
        return row
    ti = keys.index("Ticker")
    if ti + 1 >= len(values):
        return row
    logo, nxt = values[ti], values[ti + 1]
    if (
        len(logo) == 1
        and logo.isalpha()
        and logo.isupper()
        and _TICKER_RE.match(nxt or "")
        and nxt[0] == logo
    ):
        realigned = values[:ti] + values[ti + 1 :]
        return dict(zip(keys, realigned))
    return row


def parse_float(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).replace(",", "").replace("%", "").strip()
    if not cleaned or cleaned == "-":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_percent(value: str | float | int | None) -> float | None:
    return parse_float(value)


def parse_market_cap(value: str | None) -> float | None:
    """Finviz market cap like '1.23B', '456.7M', '2.1T' -> absolute float."""
    if not value or value in ("-", "--"):
        return None
    text = str(value).strip().upper().replace(",", "")
    mult = 1.0
    if text and text[-1] in ("K", "M", "B", "T"):
        mult = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}[text[-1]]
        text = text[:-1]
    try:
        return float(text) * mult
    except ValueError:
        return None


class FinvizService:
    def __init__(self, db: Session):
        self.db = db

    def _get_cache(self, key: str) -> tuple[Any, bool] | None:
        row = self.db.query(ApiCache).filter(ApiCache.cache_key == key).first()
        if not row:
            return None
        age = utcnow() - row.created_at
        payload = json.loads(row.payload)
        is_fresh = age <= timedelta(seconds=settings.cache_ttl_seconds)
        return payload, is_fresh

    def _set_cache(self, key: str, payload: Any) -> None:
        serialized = json.dumps(payload, default=str)
        row = self.db.query(ApiCache).filter(ApiCache.cache_key == key).first()
        if row:
            row.payload = serialized
            row.created_at = utcnow()
        else:
            row = ApiCache(cache_key=key, payload=serialized)
            self.db.add(row)
        self.db.commit()

    def _cached_fetch(
        self, key: str, fetcher: Callable[[], Any], *, allow_stale: bool = True
    ) -> tuple[Any, bool]:
        cached = self._get_cache(key)
        if cached:
            payload, is_fresh = cached
            if is_fresh:
                return payload, False

        try:
            payload = fetcher()
            self._set_cache(key, payload)
            return payload, False
        except Exception:
            if cached and allow_stale:
                return cached[0], True
            raise

    def get_stock_raw(self, ticker: str) -> tuple[dict[str, Any], bool]:
        ticker = ticker.upper().strip()
        key = f"stock:{ticker}"

        def fetch() -> dict[str, Any]:
            return finviz.get_stock(ticker)

        return self._cached_fetch(key, fetch)

    def get_news(self, ticker: str) -> tuple[list[tuple], bool]:
        ticker = ticker.upper().strip()
        key = f"news:{ticker}"

        def fetch() -> list[tuple]:
            return finviz.get_news(ticker)

        return self._cached_fetch(key, fetch)

    def get_analyst_targets(self, ticker: str) -> tuple[list[dict], bool]:
        ticker = ticker.upper().strip()
        key = f"analyst:{ticker}"

        def fetch() -> list[dict]:
            return finviz.get_analyst_price_targets(ticker)

        return self._cached_fetch(key, fetch)

    def get_insider(self, ticker: str) -> tuple[list[dict], bool]:
        ticker = ticker.upper().strip()
        key = f"insider:{ticker}"

        def fetch() -> list[dict]:
            return finviz.get_insider(ticker)

        return self._cached_fetch(key, fetch)

    @staticmethod
    def chart_url(ticker: str) -> str:
        ticker = ticker.upper().strip()
        return (
            f"https://finviz.com/chart.ashx?t={ticker}&ty=c&ta=1&p=d&s=l"
        )

    def run_screener(self, preset: str) -> tuple[list[dict[str, str]], bool]:
        if preset not in ALL_SCREENS:
            raise ValueError(f"Unknown screener preset: {preset}")

        config = ALL_SCREENS[preset]
        key = f"screener:{preset}"

        def fetch() -> list[dict[str, str]]:
            stock_list = Screener(
                filters=config["filters"],
                table=config["table"],
                order=config["order"],
            )
            limit = config.get("limit", 25)
            results: list[dict[str, str]] = []
            for i, stock in enumerate(stock_list):
                if i >= limit:
                    break
                results.append(_fix_screener_row(dict(stock)))
                if i > 0 and i % 20 == 0:
                    time.sleep(settings.finviz_request_delay)
            return results

        return self._cached_fetch(key, fetch)

    @staticmethod
    def extract_numeric_fields(stock: dict[str, Any]) -> dict[str, float | None]:
        return {
            "price": parse_float(stock.get("Price")),
            "rsi": parse_float(stock.get("RSI (14)")),
            "sma20": parse_percent(stock.get("SMA20")),
            "sma50": parse_percent(stock.get("SMA50")),
            "sma200": parse_percent(stock.get("SMA200")),
            "beta": parse_float(stock.get("Beta")),
            "perf_week": parse_percent(stock.get("Perf Week")),
            "perf_month": parse_percent(stock.get("Perf Month")),
            "perf_quarter": parse_percent(stock.get("Perf Quarter")),
            "perf_ytd": parse_percent(stock.get("Perf YTD")),
        }

    @staticmethod
    def median_analyst_target(targets: list[dict]) -> float | None:
        values: list[float] = []
        for target in targets:
            for field in ("target_to", "target_from", "Target"):
                val = target.get(field)
                parsed = parse_float(val)
                if parsed is not None:
                    values.append(parsed)
                    break
        if not values:
            return None
        values.sort()
        mid = len(values) // 2
        if len(values) % 2:
            return values[mid]
        return (values[mid - 1] + values[mid]) / 2

    @staticmethod
    def analyst_upside_pct(current_price: float | None, median_target: float | None) -> float | None:
        if current_price is None or median_target is None or current_price == 0:
            return None
        return round(((median_target - current_price) / current_price) * 100, 2)
