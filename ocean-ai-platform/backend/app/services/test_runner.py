# 파일 역할: 자동 검증 실행 결과를 모읍니다.
import time
import traceback
from app.core.database import SessionLocal
from app.models.domain import TestAutomationLog, TestScenario
from app.services.anomaly_detector import check_for_anomalies
from app.agents.automation_agent import AutomationAgent

def run_test_scenario(scenario_id: int):
    """
    모의 데이터(Mock)를 생성하여 6대 시나리오 워크플로우를 실행하고
    그 결과를 테스트 로그에 기록합니다.
    """
    db = SessionLocal()
    start_time = time.time()
    log_entry = TestAutomationLog(scenario_id=scenario_id, status="RUNNING", logs="")
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    
    logs = []
    agent = AutomationAgent()
    
    try:
        # Mock Data 생성
        mock_system_metrics = {"collection_rate": 85, "latency_ms": 1200}
        mock_qc_data = {"error_count": 15}
        mock_observations = [
            {"station_name": "가덕도", "tide_level": 850, "tide_deviation": 60, "sensor_status": "OK"},
            {"station_name": "덕적도", "tide_level": 400, "tide_deviation": 10, "sensor_status": "ERROR"}
        ]
        
        logs.append("[Step 1] 모의 데이터 로드 완료")
        
        # Anomaly Detection
        anomalies = check_for_anomalies(mock_observations, mock_qc_data, mock_system_metrics)
        logs.append(f"[Step 2] 이상 탐지 완료: {len(anomalies)}건 감지됨")
        
        # Agent Analysis & Report Generation
        for anomaly in anomalies:
            logs.append(f"[Step 3] '{anomaly['type']}' 이슈에 대한 Agent RAG 분석 시작...")
            task_id = agent.handle_anomaly(anomaly)
            logs.append(f"[Step 3] 완료. 생성된 결재 대기 Task ID: {task_id}")
            
        # 성공 처리
        log_entry.status = "SUCCESS"
        logs.append("[Final] 모든 워크플로우 정상 수행 완료")
        
    except Exception as e:
        log_entry.status = "FAILED"
        logs.append(f"[Error] {str(e)}")
        logs.append(traceback.format_exc())
        
    finally:
        execution_time = int((time.time() - start_time) * 1000)
        log_entry.execution_time_ms = execution_time
        log_entry.logs = "\n".join(logs)
        db.commit()
        db.refresh(log_entry)
        db.close()
        
    return {
        "log_id": log_entry.id,
        "status": log_entry.status,
        "execution_time_ms": execution_time,
        "logs": log_entry.logs
    }

def init_mock_scenarios():
    db = SessionLocal()
    try:
        if db.query(TestScenario).count() == 0:
            scenarios = [
                TestScenario(name="수집률 저하 탐지 및 분석", trigger_condition="수집률 < 90%", expected_outcome="COLLECTION_DROP 알림 등록 및 보고서 생성"),
                TestScenario(name="QC 오류 급증 자동 분석", trigger_condition="QC Error > 10", expected_outcome="QC_ERROR_SPIKE 이슈 등록"),
                TestScenario(name="바다누리 서비스 응답 지연", trigger_condition="latency > 1000ms", expected_outcome="SERVICE_DELAY 분석 초안"),
                TestScenario(name="대조기 해수면 위험 수위", trigger_condition="조위 > 800", expected_outcome="SPRING_TIDE_RISK 경보 발생"),
                TestScenario(name="주간 조위 편차 이상", trigger_condition="편차 > 50", expected_outcome="TIDE_DEVIATION 분석 리포트"),
                TestScenario(name="센서 장비 점검 발생", trigger_condition="status == ERROR", expected_outcome="EQUIPMENT_ISSUE 권고안 생성")
            ]
            db.bulk_save_objects(scenarios)
            db.commit()
    finally:
        db.close()
