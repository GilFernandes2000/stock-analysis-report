import re

# Yahoo Finance / European exchange suffixes
EU_EXCHANGE_SUFFIXES: tuple[str, ...] = (
    ".DE",
    ".L",
    ".PA",
    ".AS",
    ".SW",
    ".MI",
    ".MC",
    ".CO",
    ".HE",
    ".ST",
    ".BR",
    ".VI",
    ".OL",
    ".IR",
    ".LS",
    ".BE",
    ".F",
    ".TO",
    ".AX",
)

# Common local symbols -> Yahoo Finance ticker (when Finviz has no match)
EU_TICKER_ALIASES: dict[str, str] = {
    "BMW": "BMW.DE",
    "SAP": "SAP.DE",
    "SIEMENS": "SIE.DE",
    "SIE": "SIE.DE",
    "NESN": "NESN.SW",
    "NESTLE": "NESN.SW",
    "LVMH": "MC.PA",
    "MC": "MC.PA",
    "OR": "OR.PA",
    "LOREAL": "OR.PA",
    "ASML": "ASML.AS",
    "SHELL": "SHELL.L",
    "SHEL": "SHEL.L",
    "BP": "BP.L",
    "VODAFONE": "VOD.L",
    "AIRBUS": "AIR.PA",
    "AIR": "AIR.PA",
    "SAN": "SAN.MC",
    "BBVA": "BBVA.MC",
    "ING": "ING.AS",
    "PHIA": "PHIA.AS",
    "NOVO": "NOVO-B.CO",
    "NOVO-B": "NOVO-B.CO",
}

_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,31}$")


def normalize_ticker(raw: str) -> str:
    return raw.strip().upper().replace(" ", "")


def is_valid_ticker(ticker: str) -> bool:
    return bool(_TICKER_RE.match(ticker))


def has_exchange_suffix(ticker: str) -> bool:
    upper = ticker.upper()
    return any(upper.endswith(suffix) for suffix in EU_EXCHANGE_SUFFIXES)


def is_likely_european(ticker: str) -> bool:
    upper = normalize_ticker(ticker)
    return has_exchange_suffix(upper) or upper in EU_TICKER_ALIASES


def resolve_ticker_candidates(raw: str) -> list[str]:
    """Return ordered ticker symbols to try (deduplicated)."""
    normalized = normalize_ticker(raw)
    if not normalized:
        return []

    candidates: list[str] = [normalized]

    if normalized in EU_TICKER_ALIASES:
        candidates.append(EU_TICKER_ALIASES[normalized])

    # If user passed alias value already, also try as-is
    if has_exchange_suffix(normalized) and normalized not in candidates:
        candidates.insert(0, normalized)

    seen: set[str] = set()
    ordered: list[str] = []
    for symbol in candidates:
        if symbol not in seen:
            seen.add(symbol)
            ordered.append(symbol)
    return ordered
