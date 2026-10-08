# 파일 역할: 관측값의 이상 후보를 계산합니다.
import os

def check_for_anomalies(observations, qc_data, system_metrics):
    """
    6대 시나리오 자동 탐지 (수집률 저하, QC 오류, 서비스 지연, 대조기, 조위편차, 장비점검)
    """
    anomalies = []
    
    # 1. 수집률 저하 탐지
    if system_metrics.get('collection_rate', 100) < 90:
        anomalies.append({
            "type": "COLLECTION_DROP",
            "message": f"데이터 수집률 저하 발생 ({system_metrics.get('collection_rate')}%)",
            "severity": "HIGH"
        })
        
    # 2. QC 오류 증가 탐지
    if qc_data.get('error_count', 0) > 10:
        anomalies.append({
            "type": "QC_ERROR_SPIKE",
            "message": f"QC 오류 임계치 초과 (현재 {qc_data.get('error_count')}건)",
            "severity": "MEDIUM"
        })
        
    # 3. 서비스 지연 탐지
    if system_metrics.get('latency_ms', 0) > 1000:
        anomalies.append({
            "type": "SERVICE_DELAY",
            "message": "바다누리 해양정보서비스 응답 지연 탐지 (1000ms 초과)",
            "severity": "HIGH"
        })
        
    # 4. 대조기 위험 탐지
    for obs in observations:
        if obs.get('tide_level', 0) > 800: # 예시 수치
            anomalies.append({
                "type": "SPRING_TIDE_RISK",
                "message": f"{obs.get('station_name', 'Unknown')} 관측소 대조기 조위 위험수위 도달",
                "severity": "CRITICAL"
            })
            
    # 5. 조위편차 이상 탐지
    for obs in observations:
        if abs(obs.get('tide_deviation', 0)) > 50:
            anomalies.append({
                "type": "TIDE_DEVIATION",
                "message": f"{obs.get('station_name', 'Unknown')} 관측소 조위 편차 이상 발생",
                "severity": "MEDIUM"
            })
            
    # 6. 장비점검 이슈 탐지
    for obs in observations:
        if obs.get('sensor_status') == 'ERROR':
            anomalies.append({
                "type": "EQUIPMENT_ISSUE",
                "message": f"{obs.get('station_name', 'Unknown')} 센서 에러 상태",
                "severity": "HIGH"
            })
            
    return anomalies
