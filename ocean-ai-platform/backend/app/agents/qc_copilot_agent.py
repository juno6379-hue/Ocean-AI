"""Legacy LangGraph adapter for deterministic, evidence-bound QC review."""
from app.agents.state import AgentState
from app.services.qc_review_agent import review_bundle


def get_ai_explanation(anomaly: dict) -> str:
    """Compatibility entry point: never invent a cause or model confidence."""
    return "검토 후보입니다. 원천 QC, 재검사 결과, 문서 사건, 센서 유효기간을 확인해야 하며 최종 판정은 승인 전 미정입니다."


def detect_anomalies_node(state: AgentState) -> dict:
    raw_data = state.get("raw_data", [])
    review = review_bundle(raw_data, state.get("qc_evidence"), state.get("qc_rechecks"))
    # Recorded flags lack a verified rule/codebook applicability contract here.
    # Preserve them in review.current_recheck; no new anomaly classification.
    anomalies = []
    return dict(anomalies=anomalies, qc_metrics=dict(total_data=len(raw_data), anomaly_count=len(anomalies),
                normal_ratio=None, ai_accuracy=None, evaluated_count=None, review=review),
                messages=["QC 근거 검토 완료: 재검사·최종 QC 승인과 구분하며 미평가 자료는 정상으로 집계하지 않습니다."])
