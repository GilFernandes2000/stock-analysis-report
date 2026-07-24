import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import REPORT_TYPES
from app.database import get_db
from app.models.portfolio import Portfolio
from app.models.report import Report
from app.models.user import User
from app.schemas.report import ReportDetail, ReportGenerateRequest, ReportSummary
from app.services.auth import get_current_user
from app.services.report_builder import ReportBuilder
from app.services.tearsheet import TearsheetBuilder

router = APIRouter(prefix="/reports", tags=["reports"])


class TearsheetRequest(BaseModel):
    portfolio_ids: list[int]


def _to_detail(report: Report) -> ReportDetail:
    return ReportDetail(
        id=report.id,
        kind=report.kind,
        report_type=report.report_type,
        title=report.title,
        content_json=json.loads(report.content_json),
        content_markdown=report.content_markdown,
        created_at=report.created_at,
    )


@router.get("", response_model=list[ReportSummary])
def list_reports(
    kind: str | None = None,
    report_type: str | None = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Report).order_by(Report.created_at.desc())
    # market reports are shared; portfolio tearsheets are private to their owner
    query = query.filter(
        (Report.kind != "portfolio") | (Report.user_id == user.id)
    )
    if kind:
        query = query.filter(Report.kind == kind)
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
def get_report(
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.kind == "portfolio" and report.user_id != user.id:
        raise HTTPException(status_code=404, detail="Report not found")
    return _to_detail(report)


@router.delete("/{report_id}", status_code=204)
def delete_report(
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.kind == "portfolio" and report.user_id != user.id:
        raise HTTPException(status_code=404, detail="Report not found")
    db.delete(report)
    db.commit()


@router.post("/generate", response_model=list[ReportDetail])
def generate_reports(
    body: ReportGenerateRequest | None = None,
    user: User = Depends(get_current_user),
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


@router.post("/tearsheet", response_model=ReportDetail)
def generate_tearsheet(
    body: TearsheetRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not body.portfolio_ids:
        raise HTTPException(status_code=422, detail="Select at least one portfolio")
    portfolios = (
        db.query(Portfolio)
        .filter(Portfolio.id.in_(body.portfolio_ids), Portfolio.user_id == user.id)
        .all()
    )
    if len(portfolios) != len(set(body.portfolio_ids)):
        raise HTTPException(status_code=404, detail="Portfolio not found")
    empty = [p.name for p in portfolios if not p.transactions]
    if empty:
        raise HTTPException(
            status_code=422,
            detail=f"No transactions in: {', '.join(empty)} — import data first",
        )
    try:
        report = TearsheetBuilder(db).build(user.id, portfolios)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _to_detail(report)
