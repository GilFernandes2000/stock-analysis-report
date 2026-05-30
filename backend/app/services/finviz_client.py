import json
import time
from datetime import datetime, timedelta
from collections.abc import Callable
from typing import Any

import finviz
from finviz.screener import Screener
from sqlalchemy.orm import Session

from app.config import SCREENER_PRESETS, settings
from app.models.cache import ApiCache


def _parse_float(value: str | float | int | None) -> float | None:
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


def _parse_percent(value: str | float | int | None) -> float | None:
    return _parse_float(value)


class FinvizService:
    def __init__(self, db: Session):
        self.db = db

    def _get_cache(self, key: str) -> tuple[Any, bool] | None:
        row = self.db.query(ApiCache).filter(ApiCache.cache_key == key).first()
        if not row:
            return None
        age = datetime.utcnow() - row.created_at
        payload = json.loads(row.payload)
        is_fresh = age <= timedelta(seconds=settings.cache_ttl_seconds)
        return payload, is_fresh

    def _set_cache(self, key: str, payload: Any) -> None:
        serialized = json.dumps(payload, default=str)
        row = self.db.query(ApiCache).filter(ApiCache.cache_key == key).first()
        if row:
            row.payload = serialized
            row.created_at = datetime.utcnow()
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
        if preset not in SCREENER_PRESETS:
            raise ValueError(f"Unknown screener preset: {preset}")

        config = SCREENER_PRESETS[preset]
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
                results.append(dict(stock))
                if i > 0 and i % 20 == 0:
                    time.sleep(settings.finviz_request_delay)
            return results

        return self._cached_fetch(key, fetch)

    @staticmethod
    def extract_numeric_fields(stock: dict[str, Any]) -> dict[str, float | None]:
        return {
            "price": _parse_float(stock.get("Price")),
            "rsi": _parse_float(stock.get("RSI (14)")),
            "sma20": _parse_percent(stock.get("SMA20")),
            "sma50": _parse_percent(stock.get("SMA50")),
            "sma200": _parse_percent(stock.get("SMA200")),
            "beta": _parse_float(stock.get("Beta")),
            "perf_week": _parse_percent(stock.get("Perf Week")),
            "perf_month": _parse_percent(stock.get("Perf Month")),
            "perf_quarter": _parse_percent(stock.get("Perf Quarter")),
            "perf_ytd": _parse_percent(stock.get("Perf YTD")),
        }

    @staticmethod
    def median_analyst_target(targets: list[dict]) -> float | None:
        values: list[float] = []
        for target in targets:
            for field in ("target_to", "target_from", "Target"):
                val = target.get(field)
                parsed = _parse_float(val)
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
