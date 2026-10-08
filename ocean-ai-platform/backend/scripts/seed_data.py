# 파일 역할: 개발용 초기 예제 자료를 생성합니다.
import os
import sys
from datetime import datetime, timedelta
import random

# Add app to path so we can import from app
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import engine, Base, SessionLocal
from app.models.domain import (
    StationMetadata, SensorMetadata, ObservationRaw, QCFlagHistory, 
    OperationLog, ModelRegistry, AIReport, RetrainingHistory, AIPredictionResult
)

def init_db():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")

def seed_data():
    db = SessionLocal()
    
    # Check if already seeded
    if db.query(StationMetadata).first():
        print("Data already seeded.")
        return

    print("Seeding stations...")
    stations = [
        {"id": "DT_0001", "name": "후포", "sensor": "LASER"},
        {"id": "DT_0002", "name": "제주", "sensor": "LASER"},
        {"id": "DT_0003", "name": "인천", "sensor": "DOTT"},
        {"id": "DT_0004", "name": "목포", "sensor": "DOTT"},
        {"id": "DT_0005", "name": "영흥도", "sensor": "MIROS"},
        {"id": "DT_0006", "name": "가덕도", "sensor": "LASER"},
        {"id": "DT_0007", "name": "보령", "sensor": "MIROS"}
    ]
    
    station_objs = []
    for st in stations:
        station_objs.append(StationMetadata(
            station_id=st["id"],
            station_name=st["name"],
            network_type="조위관측소",
            status="ACTIVE"
        ))
    db.add_all(station_objs)
    db.commit()

    print("Seeding sensors...")
    sensor_objs = []
    for st in stations:
        # Tide level sensor
        sensor_objs.append(SensorMetadata(
            station_id=st["id"],
            sensor_id=f"TIDE_LEVEL_{st['sensor']}_{st['id']}",
            sensor_type=st["sensor"],
            variable_code="tide_level",
            status="ACTIVE"
        ))
    db.add_all(sensor_objs)
    db.commit()

    print("Seeding observations and QC history (mocking last 24 hours)...")
    now = datetime.utcnow()
    obs_objs = []
    qc_objs = []
    
    # IOC Flags: 1=정상, 3=의심, 4=오류, 9=결측
    for st in stations:
        sensor_id = f"TIDE_LEVEL_{st['sensor']}_{st['id']}"
        base_tide = random.uniform(200, 600)
        
        for i in range(24 * 6): # Every 10 mins for 24 hours
            ts = now - timedelta(minutes=10 * i)
            # Add some sine wave pattern
            import math
            val = base_tide + math.sin(i / 10.0) * 100 + random.uniform(-5, 5)
            
            # Simulate anomalies (approx 5% chance of being BAD or SUSPECT)
            status_flag = "1" # Normal
            ai_flag = "1"
            if random.random() < 0.05:
                status_flag = random.choice(["3", "4", "9"])
                val = val + random.uniform(50, 150) if status_flag != "9" else -999.0
                ai_flag = status_flag # AI agrees in most cases
            
            obs = ObservationRaw(
                station_id=st["id"],
                sensor_id=sensor_id,
                timestamp_utc=ts,
                variable_code="tide_level",
                value_raw=val,
                value_unit="cm",
                value_status="OK" if status_flag == "1" else "BAD"
            )
            obs_objs.append(obs)
            
            qc = QCFlagHistory(
                station_id=st["id"],
                sensor_id=sensor_id,
                timestamp_utc=ts,
                variable_code="tide_level",
                qc_stage="REALTIME",
                qc_flag_1st="OK" if status_flag == "1" else "FAIL",
                qc_flag_final=status_flag,
                ai_flag_candidate=ai_flag,
                qc_confidence=random.uniform(0.7, 0.99)
            )
            qc_objs.append(qc)

    # Batch insert
    db.bulk_save_objects(obs_objs)
    db.bulk_save_objects(qc_objs)
    db.commit()
    
    print("Seeding model registry...")
    db.add(ModelRegistry(
        model_name="TidePrediction_v1",
        model_type="LSTM",
        model_version="1.0.0",
        target_variable="tide_level",
        station_scope="ALL",
        status="PRODUCTION",
        metrics_json={"RMSE": 3.4, "MAE": 2.1, "F1": 0.95}
    ))
    db.commit()

    print("Seeding RetrainingHistory...")
    retraining_objs = []
    versions = ["1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6"]
    for i, v in enumerate(versions):
        retraining_objs.append(RetrainingHistory(
            training_id=f"TR_{v.replace('.', '_')}",
            base_model_id="TidePrediction_v1",
            candidate_model_id=f"TidePrediction_v{v}",
            training_end_time=now - timedelta(days=(len(versions)-i)*7),
            metrics_before_json={"RMSE": 3.5 - i*0.1, "F1": 0.78 + i*0.01},
            metrics_after_json={"RMSE": 3.4 - i*0.1, "F1": 0.79 + i*0.01}
        ))
    db.add_all(retraining_objs)
    db.commit()

    print("Seeding AIPredictionResult...")
    causes = ['센서 오염', '통신 지연', '해양 생물 부착', '장비 결함', '이물질 간섭', '일시적 노이즈']
    ai_preds = []
    for st in stations:
        for i in range(15):
            ts = now - timedelta(hours=i*2)
            cause = random.choice(causes)
            ai_preds.append(AIPredictionResult(
                station_id=st["id"],
                sensor_id=f"TIDE_LEVEL_{st['sensor']}_{st['id']}",
                timestamp_utc=ts,
                variable_code="tide_level",
                model_id="TidePrediction_v1",
                predicted_value=random.uniform(200, 600),
                anomaly_score=random.uniform(0.6, 0.99),
                recommended_flag=random.choice(["SUSPECT", "BAD"]),
                confidence=random.uniform(0.7, 0.95),
                cause_candidate=cause,
                explanation=f"{cause}으로 인한 비정상적인 데이터 패턴이 감지되었습니다."
            ))
    db.add_all(ai_preds)
    db.commit()

    print("Seeding AIReports...")
    report_types = ["weekly", "anomaly", "monthly", "quality"]
    titles = [
        "5월 4주차 해양관측소 AI 품질 평가 리포트",
        "제주 관측소 통신 장애 원인 진단 분석",
        "서해안 집중 관측 데이터 이상치 탐지 결과",
        "월간 조위 센서 성능 리포트",
        "여수 관측소 해양 생물 부착 이슈 보고"
    ]
    reports = []
    import uuid
    for i in range(8):
        reports.append(AIReport(
            report_id=f"REP-{uuid.uuid4().hex[:8]}",
            title=random.choice(titles),
            summary="이 리포트는 AI 에이전트가 자동 생성한 요약 보고서입니다.",
            created_at=now - timedelta(days=i*3),
            status="published",
            author="AI System",
            report_type=random.choice(report_types)
        ))
    db.add_all(reports)
    db.commit()

    print("Seed data creation completed!")
    db.close()

if __name__ == "__main__":
    init_db()
    seed_data()
