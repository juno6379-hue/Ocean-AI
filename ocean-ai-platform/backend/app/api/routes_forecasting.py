# 파일 역할: 조위 예측 관련 요청을 검증하고 API 응답을 제공합니다.
import datetime, uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.domain import ObservationStandard, ModelRegistry

router=APIRouter(prefix="/api/forecasting", tags=["Forecasting"])
class ForecastRequest(BaseModel):
    station_id: str
    horizon_hours: int=Field(72, ge=1, le=168)
    model_version: str="TIDE-FCST-BASELINE-1.0"

@router.post("/baseline")
def baseline(req: ForecastRequest, db: Session=Depends(get_db)):
    row=db.query(ObservationStandard).filter(ObservationStandard.station_id==req.station_id,ObservationStandard.variable_code=="TIDE").order_by(ObservationStandard.timestamp_utc.desc()).first()
    if not row or row.value_standard is None: raise HTTPException(404,"No TIDE observation")
    predictions=[{"timestamp_utc":(row.timestamp_utc+datetime.timedelta(hours=i)).isoformat(),"predicted_value":row.value_standard,"horizon_hour":i} for i in range(1,min(req.horizon_hours,168)+1)]
    return {"station_id":req.station_id,"model_version":req.model_version,"predictions":predictions,"method":"PERSISTENCE_BASELINE","trained_model":False,"status":"BASELINE","approval_required":True,"is_demo":False}

@router.get("/models")
def models(db: Session=Depends(get_db)):
    rows=db.query(ModelRegistry).filter(ModelRegistry.target_variable.in_(["TIDE","tide"])).order_by(ModelRegistry.created_at.desc()).all()
    return {"models":rows,"is_demo":False}
