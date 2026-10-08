# 파일 역할: 업무 자동화 단계의 입력과 결과를 처리합니다.
import os
import json
import chromadb
from app.core.database import SessionLocal
from app.models.domain import AgentTaskApproval

class AutomationAgent:
    def __init__(self):
        db_path = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")
        self.chroma_client = chromadb.PersistentClient(path=db_path)
        
        is_test = os.environ.get("TEST_MODE", "0") == "1"
        self.collection_name = "ocean_reports_test" if is_test else "ocean_reports_prod"
        self.collection = self.chroma_client.get_or_create_collection(name=self.collection_name)
        
    def _search_knowledge_base(self, query: str):
        # RAG 검색 시뮬레이션
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=2
            )
            return results.get('documents', [[]])[0]
        except:
            return []

    def handle_anomaly(self, anomaly: dict):
        """
        이상 이벤트가 발생하면 RAG로 유사 과거 이력을 검색하고, 
        원인 진단 및 보고서 초안을 생성한 뒤 결재 대기(PENDING) 상태로 DB에 저장합니다.
        """
        db = SessionLocal()
        try:
            # 1. RAG 기반 검색
            query = f"{anomaly['type']} {anomaly['message']} 해결방안"
            kb_results = self._search_knowledge_base(query)
            
            # 2. 원인 진단 및 보고서 초안 생성 (모의 로직)
            draft_content = {
                "anomaly_details": anomaly,
                "diagnosed_cause": "과거 이력(RAG) 분석 결과, 해당 센서 모델의 노후화 혹은 일시적 통신 장애일 확률이 높습니다.",
                "reference_reports": kb_results,
                "recommended_action": "현장 점검 및 센서 영점 재조정(Calibration) 권고",
                "generated_report_title": f"[자동생성] {anomaly['type']} 이상 보고서"
            }
            
            # 3. 자동 생성 결과물을 담당자 검토/승인 테이블에 PENDING 저장
            approval_task = AgentTaskApproval(
                task_type="REPORT_DRAFT",
                reference_id=anomaly['type'],
                content_payload=json.dumps(draft_content, ensure_ascii=False),
                status="PENDING"
            )
            
            db.add(approval_task)
            db.commit()
            return approval_task.id
        finally:
            db.close()
