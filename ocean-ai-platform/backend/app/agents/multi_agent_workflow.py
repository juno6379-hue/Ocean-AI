# 파일 역할: 품질 분석·원인 후보·근거 검색·승인 흐름을 연결합니다.
"""명시적 상태 머신 기반 Multi-Agent workflow."""
from datetime import datetime, timedelta
from typing import Any, Dict, List

from app.core.database import SessionLocal
from app.models.domain import AILabel, OperationLog, ObservationStandard, QCFlagHistory


def qc_analysis_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    values = [x.get("value") for x in state.get("raw_data", []) if x.get("value") is not None]
    anomalies = [x for x in state.get("raw_data", []) if x.get("value") is not None and (x.get("value") > 30 or x.get("value") < 5)]
    return {"qc": {"total": len(values), "anomaly_count": len(anomalies), "method": "range_rule(v1)"}, "anomalies": anomalies}


def root_cause_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        station_id = state["station_id"]
        labels = db.query(AILabel).filter(AILabel.station_id == station_id).order_by(AILabel.created_at.desc()).limit(5).all()
        operations = db.query(OperationLog).filter(OperationLog.station_id == station_id).order_by(OperationLog.event_time.desc()).limit(10).all()
        cause = labels[0].error_cause if labels else ("communication_fault" if any("COMMUNICATION" in (x.event_type or "").upper() for x in operations) else "unknown")
        confidence = labels[0].label_confidence if labels and labels[0].label_confidence is not None else 0.0
        return {"root_cause": {"error_cause": cause, "confidence": confidence, "status": "CANDIDATE"}}
    finally:
        db.close()


def rag_evidence_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from app.rag.hybrid_retriever import hybrid_search
        result = hybrid_search(state.get("query") or "관측 이상 원인 및 처리", {"station_id": state["station_id"]}, 3)
        return {"evidence": result.get("results", [])}
    except Exception:
        return {"evidence": []}


def recommendation_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    actions = ["관측값과 원천 장비 상태를 운영자가 확인"]
    cause = state.get("root_cause", {}).get("error_cause")
    if cause == "communication_fault": actions.append("통신 경로와 수집 로그 점검")
    elif cause == "sensor_degradation": actions.append("센서 교정·교체 이력 검토")
    return {"recommendations": actions, "recommendation_status": "RECOMMENDATION"}


def human_approval_gate(state: Dict[str, Any]) -> Dict[str, Any]:
    return {"human_approval": {"status": "PENDING", "required": True, "message": "운영자 승인 후 확정"}}


def report_draft_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    return {"report_draft": "\n".join([
        f"## 관측 이상 분석 초안 ({state['station_id']})",
        f"- QC 분석: {state.get('qc', {}).get('anomaly_count', 0)}건 이상 후보",
        f"- 원인 후보: {state.get('root_cause', {}).get('error_cause', 'unknown')}",
        f"- 추천 조치: {', '.join(state.get('recommendations', []))}",
        "- 상태: 운영자 승인 대기",
    ])}


def mlops_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    count = state.get("qc", {}).get("anomaly_count", 0)
    return {"mlops": {"retraining_priority": "HIGH" if count >= 10 else "NORMAL", "status": "RECOMMENDATION"}}


WORKFLOW = [
    ("QC Analysis Agent", qc_analysis_agent),
    ("Root Cause Agent", root_cause_agent),
    ("RAG Evidence Agent", rag_evidence_agent),
    ("Recommendation", recommendation_agent),
    ("Human Approval", human_approval_gate),
    ("Report Draft Agent", report_draft_agent),
    ("MLOps Agent", mlops_agent),
]


def run_multi_agent_workflow(station_id: str, sensor_id: str = "", query: str = "") -> Dict[str, Any]:
    db = SessionLocal()
    try:
        rows = db.query(ObservationStandard).filter(ObservationStandard.station_id == station_id).order_by(ObservationStandard.timestamp_utc.desc()).limit(500).all()
        state: Dict[str, Any] = {"station_id": station_id, "sensor_id": sensor_id, "query": query, "raw_data": [{"timestamp": x.timestamp_utc.isoformat(), "value": x.value_standard} for x in rows]}
    finally:
        db.close()
    logs = ["Anomaly Detected"]
    for name, agent in WORKFLOW:
        result = agent(state); state.update(result); logs.append(name)
    state["workflow"] = logs
    state["status"] = "ANALYSIS_ONLY"
    return state
