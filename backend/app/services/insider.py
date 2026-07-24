"""Insider-trading intelligence.

Turns raw insider filings (Finviz for US listings, Yahoo Finance as fallback)
into a scored signal. The heuristics follow the classic insider-trading
literature: open-market purchases are informative (insiders buy for one reason
only), cluster buying by multiple insiders is the strongest signal, C-suite
purchases beat director purchases, while sales are only weakly informative
(diversification, taxes) unless they are broad and heavily one-sided.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.cache import ApiCache
from app.schemas.stock import InsiderSignal, InsiderTrade

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_DAYS = 180
CLUSTER_WINDOW_DAYS = 90
YF_CACHE_TTL = timedelta(hours=6)

SENIOR_TITLE_TOKENS = (
    "ceo",
    "chief executive",
    "cfo",
    "chief financial",
    "coo",
    "chief operating",
    "president",
    "chairman",
    "chair of",
)


@dataclass
class NormalizedTrade:
    insider: str
    relationship: str
    action: str  # buy | sell | option | other
    value: float | None
    shares: str | None
    date: datetime | None
    raw_date: str | None = None

    @property
    def is_senior(self) -> bool:
        rel = self.relationship.lower()
        return any(token in rel for token in SENIOR_TITLE_TOKENS)


def _classify(transaction: str | None) -> str:
    text = (transaction or "").lower()
    if "option" in text or "exercise" in text:
        return "option"
    if "buy" in text or "purchase" in text:
        return "buy"
    if "sale" in text or "sell" in text:
        return "sell"
    return "other"


def _parse_value(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    if not cleaned or cleaned in ("-", "."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_finviz_date(raw: str | None, now: datetime) -> datetime | None:
    """Finviz dates look like "Dec 02 '24" (newer exports) or "Dec 02"."""
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%b %d '%y", "%b %d %Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass
    try:
        parsed = datetime.strptime(raw, "%b %d").replace(year=now.year)
        # A date "in the future" means it belongs to last year
        if parsed > now + timedelta(days=2):
            parsed = parsed.replace(year=now.year - 1)
        return parsed
    except ValueError:
        return None


def parse_finviz_rows(rows: list[dict], now: datetime | None = None) -> list[NormalizedTrade]:
    now = now or datetime.utcnow()
    trades = []
    for row in rows:
        trades.append(
            NormalizedTrade(
                insider=(row.get("Insider Trading") or row.get("insider") or "?").strip(),
                relationship=(row.get("Relationship") or "").strip(),
                action=_classify(row.get("Transaction")),
                value=_parse_value(row.get("Value ($)")),
                shares=row.get("#Shares"),
                date=_parse_finviz_date(row.get("Date"), now),
                raw_date=row.get("Date"),
            )
        )
    return trades


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def analyze_insider_activity(
    trades: list[NormalizedTrade],
    window_days: int = DEFAULT_WINDOW_DAYS,
    now: datetime | None = None,
) -> InsiderSignal:
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=window_days)
    cluster_cutoff = now - timedelta(days=CLUSTER_WINDOW_DAYS)

    # Undated rows are kept (Finviz only lists recent filings) but can't
    # contribute to recency-based signals.
    recent = [t for t in trades if t.date is None or t.date >= cutoff]

    buys = [t for t in recent if t.action == "buy"]
    sells = [t for t in recent if t.action == "sell"]
    options = [t for t in recent if t.action == "option"]

    buy_value = sum(t.value or 0.0 for t in buys)
    sell_value = sum(t.value or 0.0 for t in sells)
    buyers = {t.insider.lower() for t in buys}
    sellers = {t.insider.lower() for t in sells}
    cluster_buyers = {
        t.insider.lower() for t in buys if t.date is not None and t.date >= cluster_cutoff
    }
    senior_buys = [t for t in buys if t.is_senior]

    score = 0
    signals: list[str] = []

    if not recent:
        return InsiderSignal(
            label="No activity",
            score=0,
            window_days=window_days,
            buy_count=0,
            sell_count=0,
            buyers=0,
            sellers=0,
            buy_value=0.0,
            sell_value=0.0,
            net_value=0.0,
            signals=[],
            summary=f"No insider filings reported in the last {window_days // 30} months.",
        )

    # --- buying side (the informative side) ---
    if buyers:
        score += 20
        if len(cluster_buyers) >= 2:
            score += 20
            signals.append(
                f"Cluster buying: {len(cluster_buyers)} different insiders bought "
                f"on the open market within the last {CLUSTER_WINDOW_DAYS} days — "
                "historically the strongest insider signal."
            )
        elif len(buyers) >= 2:
            score += 10
            signals.append(
                f"{len(buyers)} different insiders bought within the last "
                f"{window_days // 30} months."
            )
        if senior_buys:
            score += 15
            top = max(senior_buys, key=lambda t: t.value or 0.0)
            signals.append(
                f"Senior executive purchase: {top.insider} ({top.relationship}) "
                + (f"bought ~${top.value:,.0f}." if top.value else "bought shares.")
            )
        if buy_value >= 1_000_000:
            score += 10
            signals.append(f"Total open-market buying of ~${buy_value:,.0f}.")
        elif buy_value > 0 and not signals:
            signals.append(f"Open-market buying of ~${buy_value:,.0f}.")

    # --- selling side (weak signal unless broad and one-sided) ---
    if sellers:
        one_sided = buy_value == 0 or sell_value > 10 * buy_value
        if len(sellers) >= 3 and one_sided:
            score -= 25
            signals.append(
                f"Broad distribution: {len(sellers)} insiders sold a combined "
                f"~${sell_value:,.0f} with no meaningful offsetting purchases."
            )
        elif sell_value >= 5_000_000 and one_sided:
            score -= 15
            signals.append(
                f"Heavy selling of ~${sell_value:,.0f} without offsetting buys."
            )
        elif not buyers:
            score -= 5
            signals.append(
                f"{len(sellers)} insider(s) sold ~${sell_value:,.0f}; isolated sales "
                "are usually routine (diversification, taxes)."
            )

    if options and not buys and not sells:
        signals.append(
            "Only option exercises reported — routine compensation activity, "
            "not a directional signal."
        )

    if score >= 25:
        label = "Bullish"
    elif score <= -20:
        label = "Bearish"
    else:
        label = "Neutral"

    net = buy_value - sell_value
    months = window_days // 30
    if label == "Bullish":
        summary = (
            f"Insiders are net buyers over the last {months} months "
            f"(${buy_value:,.0f} bought vs ${sell_value:,.0f} sold)."
        )
    elif label == "Bearish":
        summary = (
            f"Insiders are heavy net sellers over the last {months} months "
            f"(${sell_value:,.0f} sold vs ${buy_value:,.0f} bought)."
        )
    else:
        summary = (
            f"No strong insider signal in the last {months} months "
            f"({len(buys)} buys / {len(sells)} sales, net ${net:,.0f})."
        )

    return InsiderSignal(
        label=label,
        score=score,
        window_days=window_days,
        buy_count=len(buys),
        sell_count=len(sells),
        buyers=len(buyers),
        sellers=len(sellers),
        buy_value=round(buy_value, 2),
        sell_value=round(sell_value, 2),
        net_value=round(net, 2),
        signals=signals,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Source adapters
# ---------------------------------------------------------------------------


def yahoo_insider_rows(db: Session, ticker: str) -> list[dict]:
    """Insider transactions from yfinance, normalized to Finviz-style dicts.

    Cached in api_cache because yfinance has no local cache of its own.
    """
    key = f"insideryf:{ticker.upper()}"
    row = db.query(ApiCache).filter(ApiCache.cache_key == key).first()
    if row and datetime.utcnow() - row.created_at <= YF_CACHE_TTL:
        return json.loads(row.payload)

    rows: list[dict] = []
    try:
        import yfinance as yf

        frame = yf.Ticker(ticker).insider_transactions
        if frame is not None and not frame.empty:
            for _, record in frame.head(40).iterrows():
                text = str(record.get("Text") or record.get("Transaction") or "")
                start = record.get("Start Date")
                date_str = None
                if start is not None:
                    try:
                        date_str = start.strftime("%b %d '%y")
                    except Exception:
                        date_str = str(start)
                value = record.get("Value")
                rows.append(
                    {
                        "Insider Trading": str(record.get("Insider") or "?"),
                        "Relationship": str(record.get("Position") or ""),
                        "Transaction": text,
                        "Value ($)": None if value is None or str(value) == "nan" else str(value),
                        "#Shares": str(record.get("Shares") or ""),
                        "Date": date_str,
                    }
                )
    except Exception as exc:
        logger.debug("Yahoo insider fetch failed for %s: %s", ticker, exc)
        if row:  # stale cache beats nothing
            return json.loads(row.payload)

    payload = json.dumps(rows)
    if row:
        row.payload = payload
        row.created_at = datetime.utcnow()
    else:
        db.add(ApiCache(cache_key=key, payload=payload))
    db.commit()
    return rows


def get_insider_intel(
    db: Session, ticker: str
) -> tuple[InsiderSignal, list[InsiderTrade]]:
    """Signal + display rows for any ticker: Finviz first (US), Yahoo fallback."""
    from app.services.finviz_client import FinvizService

    rows: list[dict] = []
    if "." not in ticker:  # Finviz only covers US-listed symbols
        try:
            rows, _ = FinvizService(db).get_insider(ticker)
        except Exception as exc:
            logger.debug("Finviz insider fetch failed for %s: %s", ticker, exc)
    if not rows:
        rows = yahoo_insider_rows(db, ticker)

    trades = parse_finviz_rows(rows)
    signal = analyze_insider_activity(trades)
    display = [
        InsiderTrade(
            insider=r.get("Insider Trading"),
            relationship=r.get("Relationship"),
            transaction=r.get("Transaction"),
            shares=r.get("#Shares"),
            value=r.get("Value ($)"),
            date=r.get("Date"),
        )
        for r in rows[:10]
    ]
    return signal, display
