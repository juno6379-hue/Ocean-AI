# 파일 역할: 보고서 초안 단계의 입력과 결과를 처리합니다.
import os
import uuid
import datetime
from sqlalchemy.orm import Session
from app.models.domain import ReportGenerationHistory, ReportRegistry
from app.models.enums import ReportStatus, TriggerType

class ReportAgent:
    def __init__(self, db: Session):
        self.db = db
        self.template_dir = os.path.join(os.path.dirname(__file__), "../../sample_data/report_templates")

    def _load_template(self, template_name: str) -> str:
        path = os.path.join(self.template_dir, template_name)
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def generate_report(self, report_type: str, trigger_type: str, data_context: dict) -> str:
        """
        Generate report content based on data_context and save generation history.
        """
        template_map = {
            "DAILY_SITUATION": "daily_situation_template.md",
            "SERVICE_MONITORING": "service_monitoring_template.md",
            "SPRING_TIDE_MONITORING": "spring_tide_monitoring_template.md",
            "WEEKLY_TIDE_RESIDUAL": "weekly_tide_residual_template.md",
            "QUALITY_COLLECTION": "quality_collection_template.md",
            "DAILY_INSPECTION": "daily_inspection_template.md"
        }
        
        template_name = template_map.get(report_type)
        if not template_name:
            raise ValueError(f"Unknown report type: {report_type}")
            
        content = self._load_template(template_name)
        
        # Simple string replacement for templating
        for key, value in data_context.items():
            content = content.replace(f"{{{{{key}}}}}", str(value))
            
        generation_id = f"GEN-{uuid.uuid4().hex[:8].upper()}"
        report_id = f"REP-{uuid.uuid4().hex[:8].upper()}"
        
        # Save ReportRegistry as DRAFT
        new_report = ReportRegistry(
            report_id=report_id,
            report_type=report_type,
            report_title=f"{report_type} 자동 생성 보고서",
            report_date=datetime.datetime.utcnow(),
            period_start=data_context.get("period_start", datetime.datetime.utcnow()),
            period_end=data_context.get("period_end", datetime.datetime.utcnow()),
            status=ReportStatus.DRAFT.value,
            created_by="Report_Agent",
            summary=content[:200] + "..." if len(content) > 200 else content
        )
        self.db.add(new_report)
        
        # Save History
        history = ReportGenerationHistory(
            generation_id=generation_id,
            report_id=report_id,
            report_type=report_type,
            trigger_type=trigger_type,
            input_data_range=f"{data_context.get('period_start')} ~ {data_context.get('period_end')}",
            input_station_count=data_context.get("station_total", 0),
            input_issue_count=data_context.get("station_issue", 0),
            generation_status="SUCCESS",
            generated_summary=content[:500]
        )
        self.db.add(history)
        self.db.commit()
        
        return report_id

def generate_report_node(state: dict) -> dict:
    """
    LangGraph 호환 리포트 생성 노드 (이전 버전 호환성 유지용)
    """
    station_id = state.get("station_id", "UNKNOWN")
    anomalies = state.get("anomalies", [])
    review = state.get('qc_metrics',{}).get('review',{})
    causes = state.get("diagnosis_results", [])
    
    report_text = f"## 품질 검토 초안 ({station_id})\n\n담당자 미승인 · 원인 미확정\n\n"
    if not anomalies:
        report_text += "확정 이상 목록이 없습니다. 검사 미실행·근거 부족을 정상 또는 특이사항 없음으로 판정하지 않습니다."
    else:
        report_text += f"탐지된 이상치: {len(anomalies)}건\n"
        for i, cause in enumerate(causes):
            report_text += f"- 이슈 {i+1}: {cause}\n"
            
    report_text += '\n\n검토 상태: '+str(review.get('status','NOT_EVALUATED'))
    for blocker in review.get('blockers',[]):report_text+='\n- '+str(blocker)
    return {
        "final_report": report_text,
        "messages": ["미승인 검토 초안을 구성했습니다. 보고서 게시·QC 승인은 수행하지 않았습니다."]
    }
