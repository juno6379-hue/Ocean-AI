# 파일 역할: 관측소 기준정보 관련 요청을 검증하고 API 응답을 제공합니다.
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import date

from app.core.database import get_db
from app.models.domain import StationMetadata, SensorMetadata
from app.schemas.domain import Station

router = APIRouter(prefix="/api/stations", tags=["Stations"])

@router.get('/{station_id}/photograph')
def station_photograph(station_id:str):
    from app.services.station_media import photograph
    return photograph(station_id,date.today().isoformat())

@router.get("", response_model=List[Station])
def get_stations(skip: int = 0, limit: int = 100, as_of_month: str|None=Query(None,pattern=r'^(19|20)\d{2}-(0[1-9]|1[0-2])$'), db: Session = Depends(get_db)):
    stations = db.query(StationMetadata).offset(skip).limit(limit).all()
    if as_of_month is None:return stations
    from app.services.station_classification import reference_records
    records=[{column.name:getattr(row,column.name) for column in StationMetadata.__table__.columns} for row in stations]
    return reference_records(records,as_of_month)

@router.get('/catalog/classifications')
def classifications(as_of_month: str|None=Query(None,pattern=r'^(19|20)\d{2}-(0[1-9]|1[0-2])$'), db: Session=Depends(get_db)):
    from app.services.station_classification import catalog
    return catalog(db,as_of_month)

@router.get("/{station_id}", response_model=Station)
def get_station(station_id: str, db: Session = Depends(get_db)):
    station = db.query(StationMetadata).filter(StationMetadata.station_id == station_id).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    return station

@router.get("/{station_id}/profile")
def get_station_profile(station_id: str, db: Session = Depends(get_db)):
    # 관측소 정보, 센서 정보, 최근 장애 등을 통합해서 반환
    station = db.query(StationMetadata).filter(StationMetadata.station_id == station_id).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    
    sensors = db.query(SensorMetadata).filter(SensorMetadata.station_id == station_id).all()
    
    return {
        "station": station,
        "sensors": sensors,
    }
