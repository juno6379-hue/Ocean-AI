# 파일 역할: 이상 알림 관련 요청을 검증하고 API 응답을 제공합니다.
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.domain import Alert, AIPredictionResult, OperationLog

router = APIRouter(tags=["Alerts"])

@router.get("")
def get_alerts(db: Session = Depends(get_db)):
    alerts = db.query(Alert).order_by(Alert.detected_at.desc()).all()
    return {"alerts": alerts}

@router.post("/{issue_id}/resolve")
def resolve_alert(issue_id: str, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.issue_id == issue_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = "RESOLVED"
    db.commit()
    return {"status": "success"}

@router.get("/events")
def get_anomaly_events(limit: int = 50, db: Session = Depends(get_db)):
    events = []
    for row in db.query(AIPredictionResult).filter(AIPredictionResult.recommended_flag.in_(["BAD", "SUSPECT"])).order_by(AIPredictionResult.timestamp_utc.desc()).limit(min(limit, 200)).all():
        events.append({"event_type": "ANOMALY", "station_id": row.station_id, "sensor_id": row.sensor_id, "time": row.timestamp_utc, "severity": row.recommended_flag, "message": row.explanation, "is_demo": False})
    for row in db.query(OperationLog).filter(OperationLog.event_type.isnot(None)).order_by(OperationLog.event_time.desc()).limit(min(limit, 200)).all():
        events.append({"event_type": row.event_type, "station_id": row.station_id, "sensor_id": row.sensor_id, "time": row.event_time, "severity": "INFO", "message": row.event_detail, "is_demo": False})
    return {"events": events[:min(limit, 200)], "is_demo": False}
