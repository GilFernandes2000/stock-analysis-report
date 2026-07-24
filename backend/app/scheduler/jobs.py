import logging

from app.database import SessionLocal
from app.services.report_builder import ReportBuilder

logger = logging.getLogger(__name__)


def run_scheduled_reports() -> None:
    db = SessionLocal()
    try:
        builder = ReportBuilder(db)
        reports = builder.generate_all()
        logger.info("Generated %d scheduled reports", len(reports))
    except Exception:
        logger.exception("Failed to run scheduled reports")
    finally:
        db.close()
