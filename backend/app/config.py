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


settings = Settings()

SCREENER_PRESETS: dict[str, dict] = {
    "top_performers": {
        "label": "Top Performers",
        "description": "Momentum leaders with strong YTD and quarterly performance",
        "filters": ["idx_sp500", "cap_midover"],
        "table": "Performance",
        "order": "-perf_ytd",
        "limit": 25,
    },
    "technical_signals": {
        "label": "Technical Signals",
        "description": "Stocks with golden cross and positive technical setup",
        "filters": ["ta_golden_cross", "cap_midover"],
        "table": "Technical",
        "order": "-marketcap",
        "limit": 25,
    },
    "high_conviction": {
        "label": "High Conviction",
        "description": "High institutional ownership with low short interest",
        "filters": ["sh_instown_o90", "sh_short_low", "cap_midover"],
        "table": "Ownership",
        "order": "-marketcap",
        "limit": 25,
    },
    "analyst_favorites": {
        "label": "Analyst Favorites",
        "description": "Large caps with strong analyst upside potential",
        "filters": ["cap_largeover", "fa_pe_u50"],
        "table": "Valuation",
        "order": "-marketcap",
        "limit": 25,
    },
}

REPORT_TYPES = list(SCREENER_PRESETS.keys())
