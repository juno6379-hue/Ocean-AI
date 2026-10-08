# 파일 역할: 대용량 관측자료 저장 및 통계 관련 요청을 검증하고 API 응답을 제공합니다.
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.domain import DataLakeStat

router = APIRouter(prefix="/api/data-lake", tags=["Data Lake"])

@router.get("/stats")
def list_stats(lake_name: Optional[str] = None, variable_code: Optional[str] = None, station_id: Optional[str] = None, limit: int = Query(100, ge=1, le=5000), db: Session = Depends(get_db)):
    q = db.query(DataLakeStat)
    if lake_name: q = q.filter(DataLakeStat.lake_name == lake_name)
    if variable_code: q = q.filter(DataLakeStat.variable_code == variable_code.upper())
    if station_id: q = q.filter(DataLakeStat.station_id == station_id.upper())
    return {"stats": q.order_by(DataLakeStat.variable_code, DataLakeStat.period_start).limit(limit).all(), "is_demo": False}

@router.get("/summary")
def summary(lake_name: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(DataLakeStat)
    if lake_name: q = q.filter(DataLakeStat.lake_name == lake_name)
    rows = q.all()
    return {"lake_name": lake_name, "partitions": len(rows), "rows": sum(x.row_count for x in rows), "missing": sum(x.missing_count for x in rows), "variables": sorted({x.variable_code for x in rows}), "is_demo": False}
