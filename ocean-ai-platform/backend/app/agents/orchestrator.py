# 파일 역할: 에이전트 실행 순서와 상태 전이를 구성합니다.
from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.qc_copilot_agent import detect_anomalies_node
from app.agents.cause_diagnosis_agent import diagnose_cause_node
from app.agents.report_agent import generate_report_node
import datetime

from app.core.database import SessionLocal
from app.models.domain import ObservationRaw

def fetch_data_node(state: AgentState) -> dict:
    """
    관측소와 센서 ID를 기반으로 실제 DB에서 원시 데이터를 수집하는 노드
    """
    station_id = state.get("station_id")
    target_date_str = state.get("target_date")
    
    db = SessionLocal()
    try:
        if not station_id or not target_date_str:
            raise ValueError('station_id and target_date are required; no demonstration defaults')
            
        target_date = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").date()
        start_time = datetime.datetime.combine(target_date, datetime.time.min)
        end_time = datetime.datetime.combine(target_date, datetime.time.max)
        
        query = db.query(ObservationRaw).filter(
            ObservationRaw.station_id == station_id,
            ObservationRaw.timestamp_kst >= start_time,
            ObservationRaw.timestamp_kst <= end_time
        )
        if state.get('sensor_id'):query=query.filter(ObservationRaw.sensor_id==state['sensor_id'])
        if state.get('item_code'):query=query.filter(ObservationRaw.source_item_code==state['item_code'])
        records=query.order_by(ObservationRaw.timestamp_kst.asc()).limit(2001).all()
        if len(records)>2000:raise ValueError('Narrow the station/sensor/item interval; maximum 2000 observations')
        
        raw_data = []
        for r in records:
            raw_data.append({
                "timestamp": r.timestamp_kst.strftime("%Y-%m-%d %H:%M:%S"),
                "value": r.value_raw,
                "observation_id":str(r.id),"station_id":r.station_id,"sensor_id":r.sensor_id,
                "item_code":r.source_item_code or r.variable_code,"variable_code":r.variable_code,
                "unit":r.value_unit,"source_system":r.source_system,"source_qc_flag":r.qc_flag,
                "source_mqc_flag":r.mqc_flag,"value_status":r.value_status
            })
            
        return {
            "raw_data": raw_data,
            "messages": [f"DB 데이터 수집 완료. ({len(raw_data)}건)"]
        }
    finally:
        db.close()

def create_qc_orchestrator():
    """
    QC Copilot 워크플로우를 위한 LangGraph 생성
    """
    # 1. 그래프 초기화
    workflow = StateGraph(AgentState)
    
    # 2. 노드 추가
    workflow.add_node("fetch_data", fetch_data_node)
    workflow.add_node("detect_anomalies", detect_anomalies_node)
    workflow.add_node("diagnose_cause", diagnose_cause_node)
    workflow.add_node("generate_report", generate_report_node)
    
    # 3. 엣지 연결 (흐름 정의)
    workflow.set_entry_point("fetch_data")
    workflow.add_edge("fetch_data", "detect_anomalies")
    workflow.add_edge("detect_anomalies", "diagnose_cause")
    workflow.add_edge("diagnose_cause", "generate_report")
    workflow.add_edge("generate_report", END)
    
    # 4. 컴파일
    app = workflow.compile()
    
    return app

# 싱글톤처럼 사용할 수 있게 인스턴스 생성
qc_graph = create_qc_orchestrator()
