# 파일 역할: 에이전트 사이에 전달할 상태와 문맥을 정의합니다.
from typing import TypedDict, List, Dict, Any, Optional
import operator
from typing import Annotated

class AgentState(TypedDict, total=False):
    """
    LangGraph에서 노드 간 전달되는 전체 상태 정의
    """
    station_id: str
    sensor_id: str
    target_date: str
    item_code: str
    source_group: str
    evidence: Dict[str, Any]
    rechecks: List[Dict[str, Any]]
    final_report: str
    
    # 1. 수집된 원시 데이터
    raw_data: List[Dict[str, Any]]
    
    # 2. QC Copilot (이상 탐지) 결과
    anomalies: List[Dict[str, Any]]
    qc_metrics: Dict[str, Any]
    
    # 3. 원인 진단 결과
    diagnosis_results: List[Dict[str, Any]]
    
    # 4. 최종 추천 조치사항
    recommended_actions: List[str]
    
    # 에러 또는 기타 상태 메세지
    messages: Annotated[List[str], operator.add]
