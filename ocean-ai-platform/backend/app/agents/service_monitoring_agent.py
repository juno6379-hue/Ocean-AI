# 파일 역할: 수집 서비스 상태 단계의 입력과 결과를 처리합니다.
import uuid
import datetime
from sqlalchemy.orm import Session
from app.models.domain import ServiceMonitoringLog, Alert
from app.models.enums import IssueLevel, NotificationType, IssueStatus
from app.agents.report_agent import ReportAgent

class ServiceMonitoringAgent:
    def __init__(self, db: Session):
        self.db = db
        # Thresholds can be loaded from env vars
        self.WARNING_MINUTES = 30
        self.CRITICAL_MINUTES = 60

    def check_service(self, station_id: str, station_name: str, delay_minutes: int):
        """
        Check service status and generate logs and alerts if delayed.
        """
        issue_level = IssueLevel.NORMAL.value
        api_status = "OK"
        display_status = "OK"
        
        if delay_minutes >= self.CRITICAL_MINUTES:
            issue_level = IssueLevel.CRITICAL.value
            api_status = "DELAYED"
            display_status = "ERROR"
        elif delay_minutes >= self.WARNING_MINUTES:
            issue_level = IssueLevel.WARNING.value
            api_status = "DELAYED"
            display_status = "WARNING"
            
        log_id = f"SML-{uuid.uuid4().hex[:8].upper()}"
        
        # 1. Log the monitoring result
        log = ServiceMonitoringLog(
            service_log_id=log_id,
            service_name="바다누리 해양정보서비스",
            check_time=datetime.datetime.utcnow(),
            station_id=station_id,
            station_name=station_name,
            data_latest_time=datetime.datetime.utcnow() - datetime.timedelta(minutes=delay_minutes),
            api_status=api_status,
            display_status=display_status,
            delay_minutes=delay_minutes,
            issue_level=issue_level,
            issue_detail=f"최신 관측자료 표출 {delay_minutes}분 지연 발생" if issue_level != "NORMAL" else "정상 작동 중"
        )
        self.db.add(log)
        
        alert_id = None
        # 2. Register Issue if needed
        if issue_level != IssueLevel.NORMAL.value:
            alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
            alert = Alert(
                issue_id=alert_id,
                issue_type=NotificationType.SERVICE_DELAY.value,
                issue_level=issue_level,
                station_id=station_id,
                station_name=station_name,
                title=f"바다누리 서비스 표출 지연 ({station_name})",
                description=f"최신 관측자료가 {delay_minutes}분째 표출되지 않고 있습니다.",
                status=IssueStatus.OPEN.value,
                assigned_to="운영팀"
            )
            self.db.add(alert)
            
            # 3. Create Draft Report via ReportAgent
            ra = ReportAgent(self.db)
            report_context = {
                "check_time": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "api_status": api_status,
                "delay_station_count": 1,
                "issue_detail": f"- {station_name}: {delay_minutes}분 지연 (등급: {issue_level})"
            }
            report_id = ra.generate_report("SERVICE_MONITORING", "EVENT_BASED", report_context)
            alert.related_report_id = report_id
            
        self.db.commit()
        return log_id, alert_id
