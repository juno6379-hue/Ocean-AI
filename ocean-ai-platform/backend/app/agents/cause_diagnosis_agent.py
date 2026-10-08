"""Carry reviewable evidence forward; never randomly assign a physical cause."""
from app.agents.state import AgentState

def diagnose_cause_node(state: AgentState) -> dict:
    review=state.get('qc_metrics',{}).get('review',{})
    evidence=review.get('documentary_event_support',[])
    return {'diagnosis_results':[],
        'recommended_actions':['관측 구간·물리 센서·문서 사건의 일치 여부를 담당자가 검토'],
        'messages':[f'확정 원인 없음. 문서 지지 후보 {len(evidence)}건은 인과 확정과 구분하며 신뢰도를 임의 생성하지 않습니다.']}
