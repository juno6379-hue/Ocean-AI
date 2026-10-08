# 파일 역할: 수집 서비스 상태 관련 요청을 검증하고 API 응답을 제공합니다.
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.agents.service_monitoring_agent import ServiceMonitoringAgent
from pydantic import BaseModel

router = APIRouter(tags=["ServiceMonitoring"])


@router.get('/overview')
def service_overview(from_time: datetime|None=None, to_time: datetime|None=None, db: Session=Depends(get_db)):
    from app.services.service_observability import overview
    def utc(value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    end=utc(to_time) if to_time else datetime.now(timezone.utc)
    start=utc(from_time) if from_time else end-timedelta(days=1)
    if start>end:raise HTTPException(422,'시작 시각이 종료 시각보다 늦습니다.')
    return overview(db,start,end)

class ServiceCheckRequest(BaseModel):
    station_id: str
    station_name: str
    delay_minutes: int

@router.post("/check")
def check_service(req: ServiceCheckRequest, db: Session = Depends(get_db)):
    agent = ServiceMonitoringAgent(db)
    log_id, alert_id = agent.check_service(req.station_id, req.station_name, req.delay_minutes)
    return {"status": "success", "log_id": log_id, "alert_id": alert_id}

@router.get("/logs")
def get_service_logs(db: Session = Depends(get_db)):
    from app.models.domain import ServiceMonitoringLog
    logs = db.query(ServiceMonitoringLog).order_by(ServiceMonitoringLog.check_time.desc()).limit(50).all()
    return {"logs": logs}
