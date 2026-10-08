# 파일 역할: 통합 대시보드 집계 관련 요청을 검증하고 API 응답을 제공합니다.
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Dict, Any
from app.core.database import SessionLocal
from app.models.domain import StationMetadata, ObservationRaw
import datetime

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class DashboardSummaryResponse(BaseModel):
    success: bool
    total_stations: int
    data_collection_rate: float | None
    qc_normal_rate: float
    bad_rate: float
    qc_pie_data: List[Dict[str, Any]]
    station_summary: List[Dict[str, Any]]
    network_summary: List[Dict[str, Any]] = []

@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(db: Session = Depends(get_db)):
    try:
        # 전체 관측소 수
        total_stations = db.query(StationMetadata).count()
        
        # 전체 데이터 및 상태 건수 집계
        # 데모 편의상 DB에 있는 모든 ObservationRaw를 집계
        total_obs = db.query(ObservationRaw).count()
        
        ok_obs = db.query(ObservationRaw).filter(ObservationRaw.value_status == "OK").count() if total_obs else 0
        anomaly_obs = db.query(ObservationRaw).filter(ObservationRaw.value_status == "ANOMALY").count() if total_obs else 0
        
        # 파이 차트 데이터
        qc_pie_data = [
            {"name": "정상", "value": ok_obs, "color": "#10B981"},
            {"name": "경고(이상)", "value": anomaly_obs, "color": "#EF4444"}
        ]
        
        # 비율 계산
        qc_normal_rate = round((ok_obs / total_obs) * 100, 1) if total_obs else 0.0
        bad_rate = round((anomaly_obs / total_obs) * 100, 1) if total_obs else 0.0
        data_collection_rate = None  # Expected collection schedule is not available.
        
        # 각 관측소별 최신 데이터 (간단 구현)
        stations = db.query(StationMetadata).all()
        station_summary = []
        for st in stations:
            # 최신 관측값 1개 가져오기
            latest_obs = db.query(ObservationRaw).filter(
                ObservationRaw.station_id == st.station_id
            ).order_by(ObservationRaw.timestamp_kst.desc()).first()
            
            val = latest_obs.value_raw if latest_obs else "자료 없음"
            qc_status = "정상"
            qc_color = "text-emerald-600 bg-emerald-50 border-emerald-200"
            if latest_obs and latest_obs.value_status == "ANOMALY":
                qc_status = "경고"
                qc_color = "text-red-600 bg-red-50 border-red-200"
                
            station_summary.append({
                "station_id": st.station_id,
                "network_code": st.station_id.split('_', 1)[0] if '_' in st.station_id else st.station_id,
                "name": st.station_name,
                "network_type": st.network_type or "미상",
                "sea_area": st.sea_area or "미상",
                "latitude": st.latitude,
                "longitude": st.longitude,
                "status": st.status or "UNKNOWN",
                "val": str(val),
                "rate": "미산정",
                "qc": qc_status,
                "diff": "최근",
                "diffColor": "text-blue-500",
                "qcColor": qc_color
            })
            
        network_counts = {}
        network_normal = {}
        for st in stations:
            network = st.network_type or "미상"
            network_counts[network] = network_counts.get(network, 0) + 1
            if (st.status or '').upper() in ('ACTIVE', '정상', ''):
                network_normal[network] = network_normal.get(network, 0) + 1
        network_summary = [
            {
                "name": network,
                "total": count,
                "normal": network_normal.get(network, 0),
                "operating_rate": round(network_normal.get(network, 0) / count * 100, 1) if count else 0.0,
            }
            for network, count in sorted(network_counts.items())
        ]

        return DashboardSummaryResponse(
            success=True,
            total_stations=total_stations,
            data_collection_rate=data_collection_rate,
            qc_normal_rate=qc_normal_rate,
            bad_rate=bad_rate,
            qc_pie_data=qc_pie_data,
            station_summary=station_summary,
            network_summary=network_summary,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance")
def get_dashboard_performance():
    from app.models.domain import ModelRegistry
    with SessionLocal() as db:
        models = db.query(ModelRegistry).order_by(ModelRegistry.created_at.desc()).limit(4).all()
        return {"perfTrendData": [{"version": m.model_version, "f1": (m.metrics_json or {}).get("f1"), "rmse": (m.metrics_json or {}).get("rmse")} for m in reversed(models)], "source": "MODEL_REGISTRY"}
