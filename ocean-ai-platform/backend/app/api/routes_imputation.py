# 파일 역할: 결측 보간 관련 요청을 검증하고 API 응답을 제공합니다.
import uuid, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.domain import ObservationStandard, ObservationImputation
from app.services.long_gap_imputation import plan_long_gap_training

router=APIRouter(prefix="/api/imputation", tags=["Imputation"])

class ImputeRequest(BaseModel):
    station_id: str
    sensor_id: str
    variable_code: str = "TIDE"
    timestamp_start: datetime.datetime
    timestamp_end: datetime.datetime
    max_short_gap: int = 3

@router.get("/long-gap/detect")
def detect_long_gaps(station_id: str, sensor_id: str, variable_code: str = "TIDE", min_gap_periods: int = 4, db: Session = Depends(get_db)):
    rows=db.query(ObservationStandard).filter(ObservationStandard.station_id==station_id, ObservationStandard.sensor_id==sensor_id, ObservationStandard.variable_code==variable_code.upper()).order_by(ObservationStandard.timestamp_utc).all()
    if len(rows)<2: return {"gaps":[],"status":"INSUFFICIENT_DATA"}
    deltas=[(b.timestamp_utc-a.timestamp_utc).total_seconds() for a,b in zip(rows,rows[1:]) if b.timestamp_utc and a.timestamp_utc]
    step=sorted(deltas)[len(deltas)//2] if deltas else 60
    gaps=[]
    for a,b in zip(rows,rows[1:]):
        periods=(b.timestamp_utc-a.timestamp_utc).total_seconds()/step if step else 0
        if periods>=min_gap_periods:
            gaps.append({"start":a.timestamp_utc.isoformat(),"end":b.timestamp_utc.isoformat(),"missing_periods":max(0,int(round(periods))-1),"step_seconds":step,"model_candidates":["GRU-D","BRITS","SAITS"],"status":"CANDIDATE"})
    return {"station_id":station_id,"sensor_id":sensor_id,"variable_code":variable_code.upper(),"estimated_step_seconds":step,"gaps":gaps,"count":len(gaps),"status":"ANALYSIS_ONLY"}

@router.post("/run")
def run_imputation(req: ImputeRequest, db: Session=Depends(get_db)):
    rows=db.query(ObservationStandard).filter(ObservationStandard.station_id==req.station_id, ObservationStandard.sensor_id==req.sensor_id, ObservationStandard.variable_code==req.variable_code.upper(), ObservationStandard.timestamp_utc>=req.timestamp_start, ObservationStandard.timestamp_utc<=req.timestamp_end).order_by(ObservationStandard.timestamp_utc).all()
    if len(rows)<2: raise HTTPException(422,"At least two observations are required")
    created=0; candidates=[]
    for left,right in zip(rows,rows[1:]):
        if left.value_standard is None or right.value_standard is None: continue
        delta=(right.timestamp_utc-left.timestamp_utc).total_seconds()
        if delta<=0: continue
        step=delta/60
        if step<=1 or step>req.max_short_gap+1: continue
        gap=int(round(step))-1
        for i in range(1,gap+1):
            ts=left.timestamp_utc+datetime.timedelta(seconds=delta*i/(gap+1))
            value=float(left.value_standard+(right.value_standard-left.value_standard)*(i/(gap+1)))
            exists=db.query(ObservationImputation).filter(ObservationImputation.station_id==req.station_id,ObservationImputation.sensor_id==req.sensor_id,ObservationImputation.variable_code==req.variable_code.upper(),ObservationImputation.timestamp_utc==ts).first()
            if exists: continue
            db.add(ObservationImputation(imputation_id=f"IMP-{uuid.uuid4().hex}",station_id=req.station_id,sensor_id=req.sensor_id,variable_code=req.variable_code.upper(),timestamp_utc=ts,value_imputed=value,method="LINEAR_SHORT_GAP",confidence=max(0.0,1-gap/(req.max_short_gap+1)),gap_length=gap,model_version="IMPUTE-BASELINE-1.0",source_observation_before=left.observation_id,source_observation_after=right.observation_id,approval_status="PENDING")); created+=1
    db.commit(); return {"station_id":req.station_id,"sensor_id":req.sensor_id,"variable_code":req.variable_code.upper(),"observations":len(rows),"created":created,"long_gaps_deferred":True,"approval_required":True,"status":"ANALYSIS_ONLY"}

@router.get("")
def list_imputations(station_id: Optional[str]=None, approval_status: Optional[str]=None, limit: int=100, db: Session=Depends(get_db)):
    q=db.query(ObservationImputation)
    if station_id: q=q.filter(ObservationImputation.station_id==station_id)
    if approval_status: q=q.filter(ObservationImputation.approval_status==approval_status)
    return {"imputations":q.order_by(ObservationImputation.timestamp_utc.desc()).limit(min(limit,1000)).all(),"is_demo":False}

@router.post("/long-gap/plan")
def plan_long_gap(variable_code: str = "TIDE", gap_count: int = 0):
    return plan_long_gap_training(variable_code, gap_count)
