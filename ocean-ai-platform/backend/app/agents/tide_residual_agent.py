# 파일 역할: 조위 편차 분석 단계의 입력과 결과를 처리합니다.
import uuid
import datetime
from sqlalchemy.orm import Session
from app.models.domain import WeeklyTideResidualReport, SpringTideMonitoringReport, Alert
from app.models.enums import IssueLevel, NotificationType, IssueStatus, ResidualTrend
from app.agents.report_agent import ReportAgent

class TideResidualAnalysisAgent:
    def __init__(self, db: Session):
        self.db = db

    def analyze_weekly_residual(self, station_id: str, station_name: str, residuals: list):
        """
        Analyze weekly tide residuals and generate reports/alerts.
        residuals: list of float values
        """
        if not residuals:
            return None
            
        mean = sum(residuals) / len(residuals)
        max_res = max(residuals)
        min_res = min(residuals)
        
        # Simple mock logic for trend
        trend = ResidualTrend.STABLE.value
        if mean > 20:
            trend = ResidualTrend.INCREASE.value
        elif mean < -20:
            trend = ResidualTrend.DECREASE.value
            
        anomaly = abs(max_res) > 50 or abs(min_res) > 50
        
        report_id = f"WTR-{uuid.uuid4().hex[:8].upper()}"
        report = WeeklyTideResidualReport(
            report_id=report_id,
            station_id=station_id,
            station_name=station_name,
            week_start=datetime.datetime.utcnow() - datetime.timedelta(days=7),
            week_end=datetime.datetime.utcnow(),
            residual_mean=mean,
            residual_max=max_res,
            residual_min=min_res,
            residual_trend=trend,
            anomaly_detected=anomaly,
            analysis_comment="조위편차 이상 기준치 초과" if anomaly else "특이사항 없음"
        )
        self.db.add(report)
        
        if anomaly:
            alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
            alert = Alert(
                issue_id=alert_id,
                issue_type=NotificationType.TIDE_RESIDUAL_ANOMALY.value,
                issue_level=IssueLevel.WARNING.value,
                station_id=station_id,
                station_name=station_name,
                title=f"주간 조위편차 이상 탐지 ({station_name})",
                description=f"최대 편차가 {max_res}cm로 측정되어 기준치를 초과했습니다.",
                status=IssueStatus.OPEN.value,
                assigned_to="분석팀",
                related_report_id=report_id
            )
            self.db.add(alert)
            
            ra = ReportAgent(self.db)
            ra.generate_report("WEEKLY_TIDE_RESIDUAL", "SCHEDULED", {
                "week_start": report.week_start.strftime("%Y-%m-%d"),
                "week_end": report.week_end.strftime("%Y-%m-%d"),
                "residual_mean": round(mean, 2),
                "residual_max": round(max_res, 2),
                "residual_trend": trend,
                "analysis_comment": report.analysis_comment
            })
            
        self.db.commit()
        return report_id

    def analyze_spring_tide(self, station_id: str, station_name: str, obs_level: float, pred_level: float):
        """
        Analyze spring tide risk.
        """
        residual = obs_level - pred_level
        risk = IssueLevel.NORMAL.value
        
        if obs_level > 800:
            risk = IssueLevel.CRITICAL.value
        elif obs_level > 700:
            risk = IssueLevel.WARNING.value
            
        report_id = f"STM-{uuid.uuid4().hex[:8].upper()}"
        report = SpringTideMonitoringReport(
            report_id=report_id,
            spring_tide_period="7월 대조기",
            period_start=datetime.datetime.utcnow() - datetime.timedelta(days=2),
            period_end=datetime.datetime.utcnow() + datetime.timedelta(days=2),
            station_id=station_id,
            station_name=station_name,
            predicted_high_tide=pred_level,
            observed_high_tide=obs_level,
            tide_residual=residual,
            risk_level=risk,
            alert_message="침수 주의" if risk != "NORMAL" else "정상 범위",
            action_required="지자체 상황 전파 필요" if risk == "CRITICAL" else "모니터링 강화"
        )
        self.db.add(report)
        
        if risk in [IssueLevel.WARNING.value, IssueLevel.CRITICAL.value]:
            alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
            alert = Alert(
                issue_id=alert_id,
                issue_type=NotificationType.SPRING_TIDE_RISK.value,
                issue_level=risk,
                station_id=station_id,
                station_name=station_name,
                title=f"대조기 위험 관측소 알림 ({station_name})",
                description=f"관측 고조위가 {obs_level}cm로 위험 수위에 도달했습니다.",
                status=IssueStatus.OPEN.value,
                assigned_to="상황실",
                related_report_id=report_id
            )
            self.db.add(alert)
            
            ra = ReportAgent(self.db)
            ra.generate_report("SPRING_TIDE_MONITORING", "EVENT_BASED", {
                "period_start": report.period_start.strftime("%Y-%m-%d"),
                "period_end": report.period_end.strftime("%Y-%m-%d"),
                "risk_station_count": 1,
                "alert_message": f"- {station_name}: {report.alert_message} (위험도: {risk})",
                "action_required": report.action_required
            })
            
        self.db.commit()
        return report_id
