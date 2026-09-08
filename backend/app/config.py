from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_FRONTEND_DIST = _REPO_ROOT / "frontend" / "dist"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./stock_analysis.db"
    cache_ttl_seconds: int = 900  # 15 minutes
    finviz_request_delay: float = 1.0
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    serve_frontend: bool = True
    frontend_dist_path: Path = _DEFAULT_FRONTEND_DIST

    # APScheduler cron (weekdays, ET approximated as UTC-5 in comments)
    report_cron_hour: int = 11  # 6:30 AM ET ≈ 11:30 UTC (simplified to hour)
    report_cron_minute: int = 30
    portfolio_cron_hour: int = 12
    portfolio_cron_minute: int = 0

    default_display_currency: str = "EUR"
    supported_display_currencies: list[str] = ["EUR", "USD", "GBP"]


settings = Settings()

# All screens use the Overview table so the frontend can render one uniform,
# sortable column set (ticker, company, sector, market cap, P/E, price, change,
# volume) regardless of preset. The preset's `filters`/`order` still select and
# rank the stocks; richer per-stock metrics are one click away on the detail page.
SCREENER_PRESETS: dict[str, dict] = {
    "top_performers": {
        "label": "Top Performers",
        "description": "Momentum leaders with strong YTD and quarterly performance",
        "filters": ["idx_sp500", "cap_midover"],
        "table": "Overview",
        "order": "-perf_ytd",
        "limit": 30,
    },
    "technical_signals": {
        "label": "Technical Signals",
        "description": "Stocks with golden cross and positive technical setup",
        "filters": ["ta_golden_cross", "cap_midover"],
        "table": "Overview",
        "order": "-marketcap",
        "limit": 30,
    },
    "high_conviction": {
        "label": "High Conviction",
        "description": "High institutional ownership with low short interest",
        "filters": ["sh_instown_o90", "sh_short_low", "cap_midover"],
        "table": "Overview",
        "order": "-marketcap",
        "limit": 30,
    },
    "analyst_favorites": {
        "label": "Analyst Favorites",
        "description": "Large caps with reasonable valuation",
        "filters": ["cap_largeover", "fa_pe_u50"],
        "table": "Overview",
        "order": "-marketcap",
        "limit": 30,
    },
    "oversold_quality": {
        "label": "Oversold Quality",
        "description": "Profitable large caps trading oversold (RSI < 40)",
        "filters": ["cap_largeover", "fa_roe_pos", "ta_rsi_os40"],
        "table": "Overview",
        "order": "-marketcap",
        "limit": 30,
    },
    "dividend_leaders": {
        "label": "Dividend Leaders",
        "description": "Large caps with a healthy dividend yield above 3%",
        "filters": ["cap_largeover", "fa_div_o3"],
        "table": "Overview",
        "order": "-marketcap",
        "limit": 30,
    },
    "europe_germany": {
        "label": "Europe — Germany",
        "description": "German companies (Finviz ADRs and listings); use .DE suffix for local shares",
        "filters": ["geo_germany", "cap_midover"],
        "table": "Overview",
        "order": "-marketcap",
        "limit": 30,
    },
    "europe_uk": {
        "label": "Europe — United Kingdom",
        "description": "UK companies; use .L suffix for London listings (e.g. VOD.L, SHEL.L)",
        "filters": ["geo_uk", "cap_midover"],
        "table": "Overview",
        "order": "-marketcap",
        "limit": 30,
    },
    "europe_france": {
        "label": "Europe — France",
        "description": "French companies; use .PA suffix for Euronext Paris (e.g. MC.PA, OR.PA)",
        "filters": ["geo_france", "cap_midover"],
        "table": "Overview",
        "order": "-marketcap",
        "limit": 30,
    },
}

# "Movers" power the Market page — same Overview columns, ranked by daily action.
MOVER_PRESETS: dict[str, dict] = {
    "top_gainers": {
        "label": "Top Gainers",
        "description": "Largest daily percentage gains (mid-cap and up)",
        "filters": ["cap_midover", "sh_avgvol_o500"],
        "table": "Overview",
        "order": "-change",
        "limit": 30,
    },
    "top_losers": {
        "label": "Top Losers",
        "description": "Largest daily percentage declines (mid-cap and up)",
        "filters": ["cap_midover", "sh_avgvol_o500"],
        "table": "Overview",
        "order": "change",
        "limit": 30,
    },
    "most_active": {
        "label": "Most Active",
        "description": "Highest trading volume today",
        "filters": ["cap_midover"],
        "table": "Overview",
        "order": "-volume",
        "limit": 30,
    },
}

# Combined lookup for the screener service (both are run the same way).
ALL_SCREENS: dict[str, dict] = {**SCREENER_PRESETS, **MOVER_PRESETS}

# Only the curated screens are used for scheduled/market reports.
REPORT_TYPES = list(SCREENER_PRESETS.keys())
