# 파일 역할: 사용자 승인 및 검토 이력 관련 요청을 검증하고 API 응답을 제공합니다.
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import Actor, require_reviewer
from app.models.domain import ApprovalHistory, AILabel, QCFlagHistory, ReportRegistry, ModelRegistry, RetrainingPool

router = APIRouter(prefix="/api/approvals", tags=["Human Approval"])
TARGET_TYPES = {"QC_CHANGE", "AI_LABEL", "REPORT", "MODEL_DEPLOY"}

class ApprovalRequest(BaseModel):
    target_type: str
    target_id: str
    user_id: Optional[str] = None
    comment: str = ""
    changes: Dict[str, Any] = Field(default_factory=dict)

class CommentRequest(BaseModel):
    target_type: str
    target_id: str
    user_id: Optional[str] = None
    comment: str = ""

def _target(db: Session, target_type: str, target_id: str):
    if target_type == "QC_CHANGE":
        try: return db.query(QCFlagHistory).filter(QCFlagHistory.id == int(target_id)).with_for_update().first()
        except ValueError: return None
    if target_type == "AI_LABEL": return db.query(AILabel).filter(AILabel.label_id == target_id).with_for_update().first()
    if target_type == "REPORT": return db.query(ReportRegistry).filter(ReportRegistry.report_id == target_id).with_for_update().first()
    if target_type == "MODEL_DEPLOY":
        query = db.query(ModelRegistry).filter(ModelRegistry.model_version == target_id)
        return query.with_for_update().first()
    return None

def _history(db, typ, target_id, user_id, status, comment):
    row = ApprovalHistory(approval_type=typ, target_id=target_id, requested_by=user_id, approved_by=user_id if status == "APPROVED" else None, approval_status=status, comment=comment)
    db.add(row)
    db.flush()
    return row

@router.get("/pending")
def pending_approvals(db: Session = Depends(get_db)):
    items: List[Dict[str, Any]] = []
    for row in db.query(QCFlagHistory).filter(QCFlagHistory.reviewer_id.is_(None)).all(): items.append({"target_type":"QC_CHANGE","target_id":str(row.id),"status":"PENDING","data":{"station_id":row.station_id,"qc_flag_final":row.qc_flag_final}})
    for row in db.query(AILabel).filter(AILabel.review_status == "PENDING").all(): items.append({"target_type":"AI_LABEL","target_id":row.label_id,"status":"PENDING","data":{"station_id":row.station_id,"quality_label":row.quality_label,"error_cause":row.error_cause}})
    for row in db.query(ReportRegistry).filter(ReportRegistry.status.in_(["DRAFT","REVIEW"])).all(): items.append({"target_type":"REPORT","target_id":row.report_id,"status":row.status,"data":{"title":row.report_title}})
    for row in db.query(ModelRegistry).filter(ModelRegistry.status == "PENDING_APPROVAL").all(): items.append({"target_type":"MODEL_DEPLOY","target_id":row.model_version,"status":"PENDING","data":{"model_name":row.model_name,"version":row.model_version}})
    return {"approvals":items}

def _ensure_pending(target, typ):
    pending = {
        "QC_CHANGE": lambda: target.reviewer_id is None,
        "AI_LABEL": lambda: target.review_status == "PENDING",
        "REPORT": lambda: target.status in {"DRAFT", "REVIEW"},
        "MODEL_DEPLOY": lambda: target.status == "PENDING_APPROVAL",
    }
    if not pending[typ]():
        raise HTTPException(409, "Target has already been reviewed")


def _change_target(target, typ, req, status):
    if typ == "QC_CHANGE":
        if status == "APPROVED":
            flag = req.changes.get("qc_flag_final", target.qc_flag_2nd or target.qc_flag_1st)
            if flag not in {"1", "2", "3", "4", "9", "G", "S", "B", "GOOD", "SUSPECT", "BAD", "MISSING"}:
                raise HTTPException(422, "Unsupported final QC flag")
            target.qc_flag_final = flag
        target.reviewer_id = req.user_id
        target.review_comment = req.comment
    elif typ == "AI_LABEL":
        target.review_status, target.reviewer_id = status, req.user_id
    elif typ == "REPORT":
        target.status = status
        target.approved_by = req.user_id if status == "APPROVED" else None
        target.reviewed_by = req.user_id
    elif typ == "MODEL_DEPLOY":
        target.status = "APPROVED" if status == "APPROVED" else "REJECTED"


@router.post("/approve")
def approve(req: ApprovalRequest, db: Session = Depends(get_db), actor: Actor = Depends(require_reviewer)):
    req = req.model_copy(update={"user_id": actor.user_id})
    if req.target_type not in TARGET_TYPES: raise HTTPException(422, "Unsupported target_type")
    target = _target(db, req.target_type, req.target_id)
    if not target: raise HTTPException(404, "Approval target not found")
    _ensure_pending(target, req.target_type)
    if req.target_type == 'AI_LABEL':
        from app.services.event_evidence import validate_label
        if req.changes: raise HTTPException(422,'Modify the AI label before approving it')
        validate_label(target)
    _change_target(target, req.target_type, req, "APPROVED")
    if req.target_type == "AI_LABEL": db.add(RetrainingPool(pool_id=f"POOL-{uuid.uuid4().hex}", source_type="AI_LABEL", source_id=target.label_id, label_id=target.label_id, station_id=target.station_id, sensor_id=target.sensor_id, variable_code=target.variable_code, pool_status="PENDING", added_by=req.user_id, metadata_json={"comment":req.comment}))
    history = _history(db, req.target_type, req.target_id, req.user_id, "APPROVED", req.comment)
    if req.target_type == 'AI_LABEL':
        from app.models.evidence import LabelReviewSnapshot
        from app.services.event_evidence import review_payload, digest
        payload=review_payload(db,target)
        db.add(LabelReviewSnapshot(approval_id=history.id,label_id=target.label_id,payload=payload,payload_hash=digest(payload)))
    db.commit()
    return {"status":"APPROVED","target_type":req.target_type,"target_id":req.target_id}

@router.post("/reject")
def reject(req: ApprovalRequest, db: Session = Depends(get_db), actor: Actor = Depends(require_reviewer)):
    req = req.model_copy(update={"user_id": actor.user_id})
    if req.target_type not in TARGET_TYPES: raise HTTPException(422, "Unsupported target_type")
    target = _target(db, req.target_type, req.target_id)
    if not target: raise HTTPException(404, "Approval target not found")
    _ensure_pending(target, req.target_type)
    _change_target(target, req.target_type, req, "REJECTED"); _history(db, req.target_type, req.target_id, req.user_id, "REJECTED", req.comment); db.commit()
    return {"status":"REJECTED","target_type":req.target_type,"target_id":req.target_id}

@router.post("/modify")
def modify(req: ApprovalRequest, db: Session = Depends(get_db), actor: Actor = Depends(require_reviewer)):
    req = req.model_copy(update={"user_id": actor.user_id})
    target = _target(db, req.target_type, req.target_id)
    if not target: raise HTTPException(404, "Approval target not found")
    _ensure_pending(target, req.target_type)
    allowed = {"QC_CHANGE":{"qc_flag_2nd","review_comment"},"AI_LABEL":{"quality_label","error_type","error_cause","label_confidence"},"REPORT":{"report_title","summary"},"MODEL_DEPLOY":{"metrics_json"}}.get(req.target_type,set())
    if set(req.changes) - allowed:
        raise HTTPException(422, "Changes contain protected or unsupported fields")
    if req.target_type == "MODEL_DEPLOY" and "metrics_json" in req.changes:
        from app.api.routes_mlops import validate_metrics
        validate_metrics(req.changes["metrics_json"], target.target_task or "CLASSIFICATION")
    for key, value in req.changes.items():
        if key in allowed and hasattr(target,key): setattr(target,key,value)
    if req.target_type == 'AI_LABEL':
        from app.services.event_evidence import validate_label
        validate_label(target)
    _history(db, req.target_type, req.target_id, req.user_id, "MODIFIED", req.comment); db.commit(); return {"status":"MODIFIED","target_type":req.target_type,"target_id":req.target_id}

@router.post("/comment")
def comment(req: CommentRequest, db: Session = Depends(get_db), actor: Actor = Depends(require_reviewer)):
    req = req.model_copy(update={"user_id": actor.user_id})
    target = _target(db, req.target_type, req.target_id)
    if not target: raise HTTPException(404, "Approval target not found")
    if req.target_type == "QC_CHANGE": target.review_comment = req.comment
    _history(db, req.target_type, req.target_id, req.user_id, "COMMENTED", req.comment); db.commit(); return {"status":"COMMENTED","target_type":req.target_type,"target_id":req.target_id}

@router.get("/history")
def approval_history(target_type: Optional[str] = None, target_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(ApprovalHistory)
    if target_type: query = query.filter(ApprovalHistory.approval_type == target_type)
    if target_id: query = query.filter(ApprovalHistory.target_id == target_id)
    return {"history":query.order_by(ApprovalHistory.created_at.desc()).all()}
