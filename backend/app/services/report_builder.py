import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import SCREENER_PRESETS
from app.models.report import Report
from app.services.analysis import summarize_stock_for_report
from app.services.finviz_client import FinvizService
from app.services.stock_analysis import StockAnalysisService


class ReportBuilder:
    def __init__(self, db: Session):
        self.db = db
        self.finviz = FinvizService(db)
        self.stock_service = StockAnalysisService(db)

    def build_report(self, report_type: str) -> Report:
        if report_type not in SCREENER_PRESETS:
            raise ValueError(f"Unknown report type: {report_type}")

        preset = SCREENER_PRESETS[report_type]
        rows, stale = self.finviz.run_screener(report_type)

        enriched: list[dict[str, Any]] = []
        markdown_lines = [
            f"# {preset['label']}",
            "",
            f"_{preset['description']}_",
            "",
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            "",
        ]

        if stale:
            markdown_lines.append("_Note: Some data may be stale due to Finviz fetch issues._")
            markdown_lines.append("")

        for row in rows[:15]:
            ticker = row.get("Ticker", "")
            if not ticker:
                continue
            try:
                analysis = self.stock_service.analyze(ticker)
                entry = {
                    "ticker": ticker,
                    "company": row.get("Company") or analysis.company,
                    "price": row.get("Price") or analysis.price,
                    "change": row.get("Change") or analysis.change,
                    "market_cap": row.get("Market Cap") or analysis.market_cap,
                    "trend_label": analysis.trend.label,
                    "trend_score": analysis.trend.score,
                    "sentiment_label": analysis.sentiment.label,
                    "inst_own": analysis.inst_own,
                    "analyst_upside_pct": analysis.analyst_upside_pct,
                    "screener_data": row,
                }
                enriched.append(entry)
                markdown_lines.append(
                    summarize_stock_for_report(
                        ticker,
                        analysis.raw,
                        analysis.trend.model_dump(),
                        analysis.sentiment.label,
                        analysis.inst_own,
                        analysis.analyst_upside_pct,
                    )
                )
            except Exception as exc:
                entry = {
                    "ticker": ticker,
                    "error": str(exc),
                    "screener_data": row,
                }
                enriched.append(entry)
                markdown_lines.append(f"**{ticker}** — Error fetching analysis: {exc}")

        content_json = {
            "report_type": report_type,
            "label": preset["label"],
            "description": preset["description"],
            "stale": stale,
            "stocks": enriched,
            "generated_at": datetime.utcnow().isoformat(),
        }

        report = Report(
            report_type=report_type,
            title=preset["label"],
            content_json=json.dumps(content_json),
            content_markdown="\n".join(markdown_lines),
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def generate_all(self, report_types: list[str] | None = None) -> list[Report]:
        types = report_types or list(SCREENER_PRESETS.keys())
        reports = []
        for report_type in types:
            reports.append(self.build_report(report_type))
        return reports
