# 파일 역할: 보고서 등록부 관련 요청을 검증하고 API 응답을 제공합니다.
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
import datetime
import uuid

from app.core.database import get_db
from app.core.security import Actor, require_reviewer
from app.api.routes_approvals import ApprovalRequest, approve, reject
from app.models.domain import ReportRegistry
from app.models.enums import ReportStatus

router = APIRouter(tags=["Reports"])

class ReportUpdateStatusRequest(BaseModel):
    user_id: str
    comment: str = ""

@router.get("")
def get_reports(report_type: str = None, status: str = None, db: Session = Depends(get_db)):
    query = db.query(ReportRegistry)
    if report_type:
        query = query.filter(ReportRegistry.report_type == report_type)
    if status:
        query = query.filter(ReportRegistry.status == status)

    reports = query.order_by(ReportRegistry.created_at.desc()).all()
    return {"reports": reports}

@router.post("/generate")
def generate_report(report_type: str, period_start: str, period_end: str, db: Session = Depends(get_db)):
    # This will later trigger the ReportAgent
    # For now, create a DRAFT report
    report_id = f"REP-{uuid.uuid4().hex[:8].upper()}"
    new_report = ReportRegistry(
        report_id=report_id,
        report_type=report_type,
        report_title=f"{report_type} 자동 생성 보고서",
        report_date=datetime.datetime.utcnow(),
        period_start=datetime.datetime.fromisoformat(period_start),
        period_end=datetime.datetime.fromisoformat(period_end),
        status=ReportStatus.DRAFT.value,
        created_by="Report_Agent",
        summary="초안 작성 중..."
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    return {"status": "success", "report_id": new_report.report_id}

@router.post("/{report_id}/review")
def review_report(report_id: str, db: Session = Depends(get_db)):
    report = db.query(ReportRegistry).filter(ReportRegistry.report_id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status != ReportStatus.DRAFT.value:
        raise HTTPException(409, "Only draft reports can enter review")
    report.status = ReportStatus.REVIEW.value
    db.commit()
    return {"status": "success", "report": report}

@router.post("/{report_id}/approve")
def approve_report(report_id: str, req: ReportUpdateStatusRequest, db: Session = Depends(get_db), actor: Actor = Depends(require_reviewer)):
    approve(ApprovalRequest(target_type="REPORT", target_id=report_id, comment=req.comment), db, actor)
    return {"status": "success", "report": db.query(ReportRegistry).filter(ReportRegistry.report_id == report_id).first()}

@router.post("/{report_id}/reject")
def reject_report(report_id: str, req: ReportUpdateStatusRequest, db: Session = Depends(get_db), actor: Actor = Depends(require_reviewer)):
    reject(ApprovalRequest(target_type="REPORT", target_id=report_id, comment=req.comment), db, actor)
    return {"status": "success", "report": db.query(ReportRegistry).filter(ReportRegistry.report_id == report_id).first()}

@router.post("/{report_id}/publish")
def publish_report(report_id: str, db: Session = Depends(get_db), actor: Actor = Depends(require_reviewer)):
    report = db.query(ReportRegistry).filter(ReportRegistry.report_id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status != ReportStatus.APPROVED.value:
        raise HTTPException(status_code=400, detail="Only approved reports can be published")
    report.status = ReportStatus.PUBLISHED.value
    db.commit()
    return {"status": "success", "report": report}

# Add stats and list back for compatibility with current frontend (or refactor frontend later)
@router.get("/list")
def get_reports_list(db: Session = Depends(get_db)):
    reports = db.query(ReportRegistry).order_by(ReportRegistry.created_at.desc()).limit(10).all()
    result = []
    for r in reports:
        result.append({
            "id": r.report_id,
            "title": r.report_title,
            "summary": r.summary,
            "status_code": r.status,
            "author": r.created_by,
            "type": r.report_type,
            "status": {"DRAFT": "초안", "REVIEW": "승인 대기", "APPROVED": "승인 완료", "REJECTED": "반려", "PUBLISHED": "게시 완료"}.get(r.status, r.status),
            "date": r.created_at.strftime("%Y-%m-%d"),
            "statusColor": "text-emerald-600 bg-emerald-50 border-emerald-200" if r.status == ReportStatus.PUBLISHED.value else "text-amber-600 bg-amber-50 border-amber-200"
        })
    return {"reports": result}

@router.get("/stats")
def get_reports_stats(db: Session = Depends(get_db)):
    from sqlalchemy import func
    counts = db.query(ReportRegistry.report_type, func.count(ReportRegistry.report_id)).group_by(ReportRegistry.report_type).all()

    doc_type_data = []
    for r_type, count in counts:
        doc_type_data.append({"name": r_type, "value": count})

    from collections import Counter
    dates = db.query(ReportRegistry.created_at).all()
    months = Counter(date.strftime("%Y-%m") for (date,) in dates if date)
    total = sum(c[1] for c in counts)
    approved = db.query(ReportRegistry).filter(ReportRegistry.status.in_(["APPROVED", "PUBLISHED"])).count()
    pending = db.query(ReportRegistry).filter(ReportRegistry.status.in_(["DRAFT", "REVIEW"])).count()
    drafts = db.query(ReportRegistry).filter(ReportRegistry.status == "DRAFT").count()
    return {
        "monthly_trend": [{"month": month, "count": count} for month, count in sorted(months.items())],
        "doc_type_data": doc_type_data,
        "approval_rate": round(approved / total * 100, 1) if total else None,
        "total_reports": total,
        "summaryCards": {
            "total_docs": str(total),
            "this_month_docs": str(months.get(datetime.datetime.utcnow().strftime('%Y-%m'), 0)),
            "pending_docs": str(pending), "ai_draft_docs": str(drafts),
            "approved_docs": str(approved), "response_rate": "-",
        },
    }

@router.get("/{report_id}")
def get_report_detail(report_id: str, db: Session = Depends(get_db)):
    report = db.query(ReportRegistry).filter(ReportRegistry.report_id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"report": report}
