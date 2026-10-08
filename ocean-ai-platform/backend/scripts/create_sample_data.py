# 파일 역할: 개발 및 검증에 사용하는 예제 파일을 생성합니다.
import os

def create_files():
    base_dir = r"C:\AI_Observation\ocean-ai-platform\backend\sample_data"
    
    # 1. station_metadata.csv
    with open(os.path.join(base_dir, "station_metadata.csv"), "w", encoding="utf-8") as f:
        f.write("station_id,station_name,network_type\n")
        f.write("DT_0001,후포,TIDE\n")
        f.write("DT_0002,제주,TIDE\n")
        f.write("DT_0003,인천,TIDE\n")
        f.write("DT_0004,목포,TIDE\n")
        f.write("DT_0005,영흥도,TIDE\n")
        f.write("DT_0006,가덕도,TIDE\n")

    # 2. sensor_metadata.csv
    with open(os.path.join(base_dir, "sensor_metadata.csv"), "w", encoding="utf-8") as f:
        f.write("station_id,sensor_id,sensor_type\n")
        f.write("DT_0001,HUPO_LASER,LASER\n")
        f.write("DT_0002,JEJU_LASER,LASER\n")
        f.write("DT_0003,INCHEON_DOTT,DOTT\n")
        f.write("DT_0004,MOKPO_DOTT,DOTT\n")
        f.write("DT_0005,YEONGHEUNG_MIROS,MIROS\n")
        f.write("DT_0006,GADEOK_LASER,LASER\n")

    # 3. observation_raw_tide.csv (가덕도 위험수위 포함)
    with open(os.path.join(base_dir, "observation_raw_tide.csv"), "w", encoding="utf-8") as f:
        f.write("station_id,sensor_id,timestamp_kst,value_raw\n")
        f.write("DT_0006,GADEOK_LASER,2026-07-03 10:00:00,850\n") # 위험수위
        f.write("DT_0002,JEJU_LASER,2026-07-03 10:00:00,9999\n") # 튐값

    # 4. predicted_tide.csv
    with open(os.path.join(base_dir, "predicted_tide.csv"), "w", encoding="utf-8") as f:
        f.write("station_id,timestamp_kst,predicted_value\n")
        f.write("DT_0006,2026-07-03 10:00:00,800\n")
        f.write("DT_0004,2026-07-03 10:00:00,450\n")

    # 5. qc_flag_history.csv (후포 BAD 급증)
    with open(os.path.join(base_dir, "qc_flag_history.csv"), "w", encoding="utf-8") as f:
        f.write("station_id,sensor_id,timestamp_utc,qc_flag_final\n")
        for i in range(20):
            f.write(f"DT_0001,HUPO_LASER,2026-07-03 10:{i:02d}:00,B\n")

    # 6. service_monitoring_log.csv (영흥도 표출 지연)
    with open(os.path.join(base_dir, "service_monitoring_log.csv"), "w", encoding="utf-8") as f:
        f.write("station_id,station_name,delay_minutes,issue_level\n")
        f.write("DT_0005,영흥도,65,CRITICAL\n")

    # 7. daily_inspection_report.csv
    with open(os.path.join(base_dir, "daily_inspection_report.csv"), "w", encoding="utf-8") as f:
        f.write("station_id,sensor_id,equipment_status,issue_found,issue_detail\n")
        f.write("DT_0001,HUPO_LASER,ERROR,True,렌즈 오염으로 인한 반복값 발생\n")
        f.write("DT_0004,MOKPO_DOTT,NORMAL,True,센서 교체 후 영점 조정 필요\n")

    # 8. spring_tide_period.csv
    with open(os.path.join(base_dir, "spring_tide_period.csv"), "w", encoding="utf-8") as f:
        f.write("period_start,period_end,is_active\n")
        f.write("2026-07-01,2026-07-05,True\n")

    # 9. quality_collection_report_sample.csv (인천 수집률 저하)
    with open(os.path.join(base_dir, "quality_collection_report_sample.csv"), "w", encoding="utf-8") as f:
        f.write("station_id,collection_rate\n")
        f.write("DT_0003,75.5\n")

    # Templates
    templates_dir = os.path.join(base_dir, "report_templates")
    
    daily_situation = """# 국가해양관측망 일일상황보고
## 작성일: {{date}}

### 1. 종합 요약
금일 총 {{station_total}}개 관측소 중 {{station_issue}}개소에서 이슈가 발생했습니다.
전체 평균 수집률은 {{collection_rate_avg}}% 입니다.

### 2. 주요 이슈 사항
{{major_issue_summary}}

### 3. 미조치 및 권고사항
{{pending_action_summary}}
"""

    service_monitoring = """# 바다누리 해양정보서비스 모니터링 보고서
## 점검시각: {{check_time}}

### 1. 서비스 상태 요약
* **정상 작동 여부**: {{api_status}}
* **지연 발생 관측소**: {{delay_station_count}}개소

### 2. 지연 발생 상세
{{issue_detail}}

### 3. 권고 조치
지연이 확인된 관측소의 연계 서버 점검이 필요합니다.
"""

    spring_tide = """# 국가해양관측망 대조기모니터링 보고서
## 대조기 기간: {{period_start}} ~ {{period_end}}

### 1. 위험 관측소 요약
* **위험 등급(WARNING 이상)**: {{risk_station_count}}개소

### 2. 상세 내역
{{alert_message}}

### 3. 권고사항
{{action_required}}
"""

    weekly_tide = """# 주간조위편차경향보고서
## 분석 기간: {{week_start}} ~ {{week_end}}

### 1. 편차 분석 요약
* **평균 편차**: {{residual_mean}}cm
* **최대 편차**: {{residual_max}}cm
* **전주 대비 경향**: {{residual_trend}}

### 2. 이상 탐지 내역
{{analysis_comment}}
"""

    quality = """# 품질처리보고서 및 수집률 현황
## 분석 기간: {{period_start}} ~ {{period_end}}

### 1. 수집 현황
* **전체 수집률**: {{collection_rate}}%
* **예상 데이터 수**: {{total_expected_count}}건

### 2. QC 처리 결과
* 정상(OK): {{qc_normal_count}}
* 결측/오류(BAD): {{qc_bad_count}}

### 3. 종합 의견
수집률 90% 미만 관측소에 대한 현장 점검이 필요합니다.
"""

    inspection = """# 일일점검보고서
## 점검일: {{report_date}}

### 1. 점검 대상 관측소
{{station_name}} ({{sensor_id}})

### 2. 상태 점검 결과
* 장비 상태: {{equipment_status}}
* 통신 상태: {{communication_status}}
* 전원 상태: {{power_status}}

### 3. 발견된 이슈 및 조치사항
{{issue_detail}}
조치: {{action_taken}}
"""

    with open(os.path.join(templates_dir, "daily_situation_template.md"), "w", encoding="utf-8") as f: f.write(daily_situation)
    with open(os.path.join(templates_dir, "service_monitoring_template.md"), "w", encoding="utf-8") as f: f.write(service_monitoring)
    with open(os.path.join(templates_dir, "spring_tide_monitoring_template.md"), "w", encoding="utf-8") as f: f.write(spring_tide)
    with open(os.path.join(templates_dir, "weekly_tide_residual_template.md"), "w", encoding="utf-8") as f: f.write(weekly_tide)
    with open(os.path.join(templates_dir, "quality_collection_template.md"), "w", encoding="utf-8") as f: f.write(quality)
    with open(os.path.join(templates_dir, "daily_inspection_template.md"), "w", encoding="utf-8") as f: f.write(inspection)

if __name__ == "__main__":
    create_files()
