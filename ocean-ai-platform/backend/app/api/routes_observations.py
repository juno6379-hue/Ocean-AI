# 파일 역할: 관측 자료 조회 관련 요청을 검증하고 API 응답을 제공합니다.
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import random
import datetime

from app.core.database import get_db
from app.models.domain import ObservationRaw, ObservationStandard
from app.schemas.domain import ObservationRaw as ObservationRawSchema, ObservationStandard as ObservationStandardSchema

router = APIRouter(prefix="/api/observations", tags=["Observations"])

@router.get("", response_model=List[ObservationRawSchema])
def get_observations(
    station_id: Optional[str] = None,
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db)
):
    query = db.query(ObservationRaw)
    if station_id:
        query = query.filter(ObservationRaw.station_id == station_id)
    
    # 최신 자료부터 반환
    observations = query.order_by(ObservationRaw.timestamp_utc.desc()).limit(limit).all()
    return observations


@router.get("/standard", response_model=List[ObservationStandardSchema])
def get_standard_observations(
    station_id: Optional[str] = None,
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db),
):
    """표준화 완료 관측값을 조회한다. Raw API와 분리해 제공한다."""
    query = db.query(ObservationStandard)
    if station_id:
        query = query.filter(ObservationStandard.station_id == station_id)
    return query.order_by(ObservationStandard.timestamp_utc.desc()).limit(limit).all()

@router.get("/summary")
def get_observations_summary(db: Session = Depends(get_db)):
    from app.models.domain import StationMetadata
    stations = db.query(StationMetadata).all()

    def display_status(db_status: Optional[str]) -> str:
        value = (db_status or '').strip().upper()
        if value in ('ERROR', 'INACTIVE', 'OFFLINE', 'STOPPED', '중단', '정지'):
            return '중단'
        if value in ('MAINTENANCE', 'DELAY', 'DEGRADED', '지연'):
            return '지연'
        return '정상'
    
    total = len(stations)
    normal = sum(1 for s in stations if display_status(s.status) == "정상")
    delay = sum(1 for s in stations if display_status(s.status) == "지연")
    offline = sum(1 for s in stations if display_status(s.status) == "중단")

    collection_rate = round((normal / total * 100), 1) if total > 0 else 0

    summary = {
        "total": total,
        "collection_rate": None,
        "station_operating_rate": collection_rate,
        "normal": normal,
        "delay": delay,
        "offline": offline,
        "daily_count": db.query(ObservationRaw).filter(ObservationRaw.timestamp_utc >= datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)).count()
    }

    current_time = datetime.datetime.utcnow()
    chart_data = []  # Historical expected counts are not available.

    map_markers = []
    table_data = []

    for i, st in enumerate(stations):
        # Map DB status to display status
        display_stat = display_status(st.status)

        # 좌표가 없는 관측소를 대한민국 중심점에 표시하면 위치가 왜곡되므로
        # 지도 마커에서는 제외하고 표/상세 API에는 계속 노출한다.
        if st.latitude is not None and st.longitude is not None:
            map_markers.append({
                "id": st.station_id,
                "network_code": st.station_id.split('_', 1)[0] if '_' in st.station_id else st.station_id,
                "lat": st.latitude,
                "lng": st.longitude,
                "status": display_stat,
                "net": st.network_type or "미상",
                "sea": st.sea_area or "미상",
                "name": st.station_name
            })
        
        stat_color = "text-emerald-500"
        if display_stat == "지연": stat_color = "text-amber-500"
        elif display_stat == "중단": stat_color = "text-red-500"

        table_data.append({
            "station_id": st.station_id,
            "network_code": st.station_id.split('_', 1)[0] if '_' in st.station_id else st.station_id,
            "name": st.station_name,
            "net": st.network_type,
            "sea": st.sea_area,
            "rate": "미산정",
            "stat": display_stat,
            "statColor": stat_color,
            "time": "미확인",
            "delay": "미산정",
            "note": "-"
        })

    # 센서 메타데이터가 아직 동기화되지 않아도 관측소 유형 현황을 표시한다.
    network_counts = {}
    network_normal = {}
    for station in stations:
        network = station.network_type or "미상"
        network_counts[network] = network_counts.get(network, 0) + 1
        if display_status(station.status) == "정상":
            network_normal[network] = network_normal.get(network, 0) + 1

    type_status = []
    colors = ["bg-blue-600", "bg-emerald-500", "bg-purple-500", "bg-amber-500", "bg-teal-500"]
    for i, (vc, count) in enumerate(network_counts.items()):
        normal_cnt = network_normal.get(vc, 0)
        rate = round((normal_cnt / count) * 100, 1) if count > 0 else 0
        
        stat = "정상"
        stat_color = "text-emerald-500"
        if rate < 90:
            stat = "지연"
            stat_color = "text-amber-500"
        if rate < 50:
            stat = "중단"
            stat_color = "text-red-500"
            
        type_status.append({
            "name": vc,
            "rate": None,
            "station_operating_rate": rate,
            "color": colors[i % len(colors)],
            "stat": stat,
            "statColor": stat_color
        })

    recent_data = []
    notifications = []
    

    
    for st in stations:
        display_stat = display_status(st.status)

        # 최근 데이터 수신 현황
        stat_color = "text-emerald-500"
        if display_stat == "지연": stat_color = "text-amber-500"
        elif display_stat == "중단": stat_color = "text-red-500"

        latest = db.query(ObservationRaw).filter(ObservationRaw.station_id == st.station_id).order_by(ObservationRaw.timestamp_utc.desc()).first()
        time_str = latest.timestamp_utc.isoformat() + "Z" if latest and latest.timestamp_utc else "-"
        if display_stat == "중단":
            time_str = "-"
            
        recent_data.append({
            "station_id": st.station_id,
            "network_code": st.station_id.split('_', 1)[0] if '_' in st.station_id else st.station_id,
            "name": st.station_name,
            "time": time_str,
            "status": display_stat,
            "color": stat_color,
            "network_type": st.network_type
        })
        
    return {
        "summary": summary,
        "chartData": chart_data,
        "mapMarkers": map_markers,
        "tableData": table_data,
        "typeStatus": type_status,
        "recentData": recent_data,
        "notifications": notifications
    }
