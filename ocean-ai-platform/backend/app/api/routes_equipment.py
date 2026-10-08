# 파일 역할: 관측장비 및 운영 이력 관련 요청을 검증하고 API 응답을 제공합니다.
from fastapi import APIRouter
from app.core.database import SessionLocal
from app.core.config import settings
from app.models.domain import StationMetadata, SensorMetadata
import random
import datetime

router = APIRouter(prefix="/api/equipment", tags=["Equipment"])

@router.get("/status")
def get_equipment_status():
    db = SessionLocal()
    try:
        stations = db.query(StationMetadata).all()
        # 실제 데이터베이스에 관측소가 없으면 시드 데이터 개수(예: 356)로 가정
        total_equip = len(stations)

        def station_state(status):
            value = (status or '').strip().upper()
            if value in ('ERROR', 'INACTIVE', 'OFFLINE', 'STOPPED', '중단', '정지'):
                return '장애'
            if value in ('MAINTENANCE', 'DELAY', 'DEGRADED', '지연'):
                return '주의'
            return '정상'

        # 1. Summary Cards from MDC-mapped station metadata
        if stations:
            states = [station_state(s.status) for s in stations]
            normal_count = states.count('정상')
            need_check_count = states.count('주의')
            warning_count = states.count('장애')
            avg_rate = round(normal_count / len(stations) * 100, 1)
        else:
            normal_count, need_check_count, warning_count, avg_rate = 0, 0, 0, 0.0
        summary = {
            "total_equip": total_equip,
            "normal": normal_count,
            "need_check": need_check_count,
            "warning": warning_count,
            "offline_network": warning_count,
            "avg_rate": avg_rate
        }

        # 2. Status Distribution (Pie Chart)
        status_data = [
            {"name": "정상", "value": summary["normal"], "color": "#10B981"},
            {"name": "주의", "value": summary["need_check"], "color": "#F59E0B"},
            {"name": "장애", "value": summary["warning"], "color": "#EF4444"},
        ]
        for item in status_data:
            item["percent"] = f"{round(item['value'] / total_equip * 100, 1) if total_equip else 0}%"

        cause_data = []
        equip_data = [{"name": st.station_name, "type": st.network_type or "미상", "item": "미확인", "time": "미확인", "state": station_state(st.status), "stateColor": "text-slate-600", "health": None, "healthColor": "bg-slate-200", "power": "미확인", "cycle": "미확인", "note": "상태 메타데이터 기준"} for st in stations[:10]]
        if settings.DATA_MODE == "demo":
            # 3. Cause Data
            cause_data = [
                {"name": "통신 장애", "value": 5, "percent": "41.7%", "color": "#EF4444"},
                {"name": "센서 고착", "value": 3, "percent": "25.0%", "color": "#F97316"},
                {"name": "전원 문제", "value": 2, "percent": "16.7%", "color": "#EAB308"},
                {"name": "장비 노후", "value": 1, "percent": "8.3%", "color": "#22C55E"},
                {"name": "현장 점검 필요", "value": 1, "percent": "8.3%", "color": "#A855F7"},
            ]

            # 4. Equip Data (Mix DB and Mock)
            equip_data = []
            if stations:
                for s in stations[:10]: # 10개만 리스트업
                    health = random.randint(70, 100)
                    state = "정상"
                    state_color = "text-emerald-500 bg-emerald-50 border-emerald-200"
                    health_color = "bg-emerald-500"
                    if health < 80:
                        state = "주의"
                        state_color = "text-amber-500 bg-amber-50 border-amber-200"
                        health_color = "bg-amber-500"
                    if health < 50:
                        state = "장애"
                        state_color = "text-red-500 bg-red-50 border-red-200"
                        health_color = "bg-red-500"

                    equip_data.append({
                        "name": f"{s.station_name} ({s.network_type or 'LASER'})",
                        "type": s.network_type or "LASER",
                        "item": "파랑, 해수면",
                        "time": datetime.datetime.now().strftime("%m/%d %H:%M"),
                        "state": state,
                        "stateColor": state_color,
                        "health": health,
                        "healthColor": health_color,
                        "power": "AC / 100%" if health > 60 else "배터리 / 18%",
                        "cycle": "6개월",
                        "note": "-" if health > 80 else "점검 권장"
                    })
            else:
                # Fallback mock
                equip_data = [
                    {"name": "제주 (LASER)", "type": "LASER", "item": "파랑, 해수면", "time": "05/28 10:26", "state": "정상", "stateColor": "text-emerald-500 bg-emerald-50 border-emerald-200", "health": 95, "healthColor": "bg-emerald-500", "power": "AC / 100%", "cycle": "6개월", "note": "-"},
                    {"name": "인천 (DOTT)", "type": "DOTT", "item": "수온, 염분", "time": "05/28 10:24", "state": "주의", "stateColor": "text-amber-500 bg-amber-50 border-amber-200", "health": 78, "healthColor": "bg-amber-500", "power": "배터리 / 65%", "cycle": "12개월", "note": "배터리 낮음"}
                ]

        # 5. Network Data: MDC DATA_TYPE 매핑 결과를 사용
        network_counts = {}
        network_normal = {}
        for station in stations:
            network = station.network_type or "미상"
            network_counts[network] = network_counts.get(network, 0) + 1
            if station_state(station.status) == '정상':
                network_normal[network] = network_normal.get(network, 0) + 1
        network_data = [
            {
                "name": network,
                "value": round(network_normal.get(network, 0) / count * 100, 1) if count else 0.0,
                "total": count,
            }
            for network, count in sorted(network_counts.items())
        ]

        # 6. Tickets
        tickets = [
            {"id": "TKT-250528-018", "target": "가덕도 (LASER)", "issue": "배터리 저전압", "status": "긴급 대응", "statusColor": "text-red-500 border-red-200", "time": "10:18"},
            {"id": "TKT-250528-017", "target": "목포 (DOTT)", "issue": "센서 오프셋 감지", "status": "진행 중", "statusColor": "text-amber-500 border-amber-200", "time": "09:52"},
            {"id": "TKT-250528-016", "target": "인천 (DOTT)", "issue": "정기 검교정 요청", "status": "점검 요청", "statusColor": "text-amber-500 border-amber-200", "time": "09:21"},
        ]

        # 7. Alerts
        alerts = [
            {"type": "OK", "text": "후포 (LASER) 통신 재연결 완료", "time": "05/28 10:27"},
            {"type": "WARN", "text": "목포 (DOTT) 센서 오프셋 감지", "time": "05/28 10:22"},
            {"type": "DANGER", "text": "가덕도 (LASER) 배터리 저전압 경고", "time": "05/28 09:58"},
            {"type": "NETWORK", "text": "인천 (DOTT) 통신 신호 약화", "time": "05/28 09:46"},
        ]

        if settings.DATA_MODE != "demo":
            tickets, alerts = [], []
        return {
            "is_demo": settings.DATA_MODE == "demo",
            "summary": summary,
            "statusData": status_data,
            "causeData": cause_data,
            "equipData": equip_data,
            "networkData": network_data,
            "tickets": tickets,
            "alerts": alerts
        }
    finally:
        db.close()
