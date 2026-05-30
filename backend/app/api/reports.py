import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import REPORT_TYPES
from app.database import get_db
from app.models.report import Report
from app.schemas.report import (
    ReportDetail,
    ReportGenerateRequest,
    ReportSummary,
)
from app.services.report_builder import ReportBuilder

router = APIRouter(prefix="/reports", tags=["reports"])


def _to_detail(report: Report) -> ReportDetail:
    return ReportDetail(
        id=report.id,
        report_type=report.report_type,
        title=report.title,
        content_json=json.loads(report.content_json),
        content_markdown=report.content_markdown,
        created_at=report.created_at,
    )


@router.get("", response_model=list[ReportSummary])
def list_reports(
    report_type: str | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    query = db.query(Report).order_by(Report.created_at.desc())
    if report_type:
        query = query.filter(Report.report_type == report_type)
    return query.limit(limit).all()


@router.get("/latest", response_model=list[ReportDetail])
def latest_reports(db: Session = Depends(get_db)):
    results = []
    for report_type in REPORT_TYPES:
        report = (
            db.query(Report)
            .filter(Report.report_type == report_type)
            .order_by(Report.created_at.desc())
            .first()
        )
        if report:
            results.append(_to_detail(report))
    return results


@router.get("/{report_id}", response_model=ReportDetail)
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return _to_detail(report)


@router.post("/generate", response_model=list[ReportDetail])
def generate_reports(
    body: ReportGenerateRequest | None = None,
    db: Session = Depends(get_db),
):
    builder = ReportBuilder(db)
    types = body.report_types if body and body.report_types else None
    if types:
        invalid = [t for t in types if t not in REPORT_TYPES]
        if invalid:
            raise HTTPException(
                status_code=400, detail=f"Unknown report types: {invalid}"
            )
    try:
        reports = builder.generate_all(types)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [_to_detail(r) for r in reports]
