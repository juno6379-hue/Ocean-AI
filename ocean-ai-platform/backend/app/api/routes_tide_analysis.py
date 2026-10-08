# 파일 역할: 조위 분석 관련 요청을 검증하고 API 응답을 제공합니다.
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.agents.tide_residual_agent import TideResidualAnalysisAgent
from pydantic import BaseModel
from typing import List

router = APIRouter(tags=["TideAnalysis"])

class WeeklyTideRequest(BaseModel):
    station_id: str
    station_name: str
    residuals: List[float]

class SpringTideRequest(BaseModel):
    station_id: str
    station_name: str
    obs_level: float
    pred_level: float

@router.post("/tide-residual/analyze")
def analyze_tide_residual(req: WeeklyTideRequest, db: Session = Depends(get_db)):
    agent = TideResidualAnalysisAgent(db)
    report_id = agent.analyze_weekly_residual(req.station_id, req.station_name, req.residuals)
    return {"status": "success", "report_id": report_id}

@router.post("/spring-tide/analyze")
def analyze_spring_tide(req: SpringTideRequest, db: Session = Depends(get_db)):
    agent = TideResidualAnalysisAgent(db)
    report_id = agent.analyze_spring_tide(req.station_id, req.station_name, req.obs_level, req.pred_level)
    return {"status": "success", "report_id": report_id}
