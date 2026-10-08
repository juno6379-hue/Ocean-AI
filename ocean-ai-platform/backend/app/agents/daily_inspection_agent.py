# 파일 역할: 일일 점검 단계의 입력과 결과를 처리합니다.
import uuid
import datetime
from sqlalchemy.orm import Session
from app.models.domain import DailyInspectionReport, Alert
from app.models.enums import NotificationType, IssueLevel, IssueStatus
from app.agents.report_agent import ReportAgent

class DailyInspectionAgent:
    def __init__(self, db: Session):
        self.db = db

    def register_inspection(self, data: dict):
        """
        Register a daily inspection report.
        """
        inspection_id = f"DIR-{uuid.uuid4().hex[:8].upper()}"
        
        issue_found = data.get("issue_found", False)
        
        report = DailyInspectionReport(
            inspection_id=inspection_id,
            report_date=datetime.datetime.utcnow(),
            station_id=data.get("station_id"),
            station_name=data.get("station_name"),
            sensor_id=data.get("sensor_id"),
            equipment_status=data.get("equipment_status", "NORMAL"),
            communication_status=data.get("communication_status", "NORMAL"),
            power_status=data.get("power_status", "NORMAL"),
            issue_found=issue_found,
            issue_detail=data.get("issue_detail", ""),
            action_taken=data.get("action_taken", ""),
            inspector=data.get("inspector", "SYSTEM"),
            follow_up_required=data.get("follow_up_required", False)
        )
        self.db.add(report)
        
        if report.follow_up_required:
            alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
            alert = Alert(
                issue_id=alert_id,
                issue_type=NotificationType.EQUIPMENT_INSPECTION_REQUIRED.value,
                issue_level=IssueLevel.WARNING.value,
                station_id=report.station_id,
                station_name=report.station_name,
                title=f"장비 후속 조치 필요 ({report.station_name})",
                description=f"일일점검 중 이슈가 발견되어 조치가 필요합니다: {report.issue_detail}",
                status=IssueStatus.OPEN.value,
                assigned_to="유지보수팀"
            )
            self.db.add(alert)
            
            ra = ReportAgent(self.db)
            ra.generate_report("DAILY_INSPECTION", "MANUAL", {
                "report_date": report.report_date.strftime("%Y-%m-%d"),
                "station_name": report.station_name,
                "sensor_id": report.sensor_id,
                "equipment_status": report.equipment_status,
                "communication_status": report.communication_status,
                "power_status": report.power_status,
                "issue_detail": report.issue_detail,
                "action_taken": report.action_taken
            })
            
        self.db.commit()
        return inspection_id
