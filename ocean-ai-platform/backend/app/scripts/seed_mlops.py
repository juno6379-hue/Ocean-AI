# 파일 역할: 개발용 모델 운영 예제 자료를 구성합니다.
import sys
import os
import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.database import SessionLocal, engine
from app.models.domain import Base, ModelRegistry, RetrainingHistory

def seed_mlops_data():
    db = SessionLocal()
    
    # 테이블 생성 (혹시 없으면)
    Base.metadata.create_all(bind=engine)
    
    # 이미 데이터가 있으면 패스
    if db.query(ModelRegistry).count() > 0:
        print("MLOps seed data already exists.")
        db.close()
        return

    now = datetime.datetime.now()
    
    models = [
        ModelRegistry(
            model_id="M_TIDE_QC_01",
            model_name="조위 AI 품질처리 모델",
            version="v2.3",
            target_variable="TIDE",
            description="전국 50개 관측소 조위 이상치 탐지 및 자동 품질처리 보정 모델",
            status="ACTIVE",
            performance_metrics='{"F1": 0.93, "RMSE": 4.1}',
            deployed_at=now - datetime.timedelta(days=5),
            deployed_by="system"
        ),
        ModelRegistry(
            model_id="M_WAVE_ANOMALY_01",
            model_name="파고 이상탐지 모델",
            version="v0.9",
            target_variable="WAVE",
            description="동해안 특화 부이 파고 이상탐지",
            status="RETRAIN_REQUIRED",
            performance_metrics='{"F1": 0.84, "RMSE": 6.7}',
            deployed_at=now - datetime.timedelta(days=20),
            deployed_by="system"
        ),
        ModelRegistry(
            model_id="M_FLOW_HF_01",
            model_name="HF-Radar 유속장 모델",
            version="v1.1",
            target_variable="FLOW",
            description="남해권 고주파 레이더 기반 유속장 예측 모델",
            status="ACTIVE",
            performance_metrics='{"F1": 0.89, "RMSE": 5.1}',
            deployed_at=now - datetime.timedelta(days=10),
            deployed_by="admin"
        ),
        ModelRegistry(
            model_id="M_TIDE_JEJU_01",
            model_name="제주 조위 특화 모델",
            version="v1.5",
            target_variable="TIDE",
            description="제주권역 (LASER) 조위 특화 예측 모델",
            status="ACTIVE",
            performance_metrics='{"F1": 0.92, "RMSE": 4.3}',
            deployed_at=now - datetime.timedelta(days=15),
            deployed_by="admin"
        ),
        ModelRegistry(
            model_id="M_TIDE_HUPO_01",
            model_name="후포 조위 특화 모델",
            version="v1.8",
            target_variable="TIDE",
            description="후포 관측소 특화 조위 보정 모델",
            status="VALIDATING",
            performance_metrics='{"F1": 0.91, "RMSE": 4.8}',
            deployed_at=now - datetime.timedelta(days=2),
            deployed_by="admin"
        ),
    ]
    
    db.add_all(models)
    db.commit()

    retrain_history = [
        RetrainingHistory(
            training_id="TR-20250527-001",
            model_id="M_TIDE_QC_01",
            start_time=now - datetime.timedelta(days=6, hours=10),
            end_time=now - datetime.timedelta(days=6, hours=2),
            status="COMPLETED",
            new_version="v2.3",
            data_range_start=now - datetime.timedelta(days=365),
            data_range_end=now - datetime.timedelta(days=6),
            performance_before='{"F1": 0.91, "RMSE": 4.6}',
            performance_after='{"F1": 0.93, "RMSE": 4.1}',
            triggered_by="admin"
        ),
        RetrainingHistory(
            training_id="TR-20250522-003",
            model_id="M_FLOW_HF_01",
            start_time=now - datetime.timedelta(days=11, hours=8),
            end_time=now - datetime.timedelta(days=11, hours=3),
            status="COMPLETED",
            new_version="v1.1",
            data_range_start=now - datetime.timedelta(days=180),
            data_range_end=now - datetime.timedelta(days=11),
            performance_before='{"F1": 0.87, "RMSE": 5.4}',
            performance_after='{"F1": 0.89, "RMSE": 5.1}',
            triggered_by="system_auto"
        )
    ]
    
    db.add_all(retrain_history)
    db.commit()
    
    print("MLOps 시드 데이터가 성공적으로 주입되었습니다.")
    db.close()

if __name__ == "__main__":
    seed_mlops_data()
