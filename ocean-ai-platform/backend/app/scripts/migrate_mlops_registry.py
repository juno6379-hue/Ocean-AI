# 파일 역할: 모델 및 재학습 등록부의 스키마 변경을 반영합니다.
from sqlalchemy import inspect, text
from app.core.database import engine

MODEL_COLUMNS = {
    "dataset_version": "VARCHAR", "feature_version": "VARCHAR", "label_version": "VARCHAR",
    "preprocessing_version": "VARCHAR", "deployment_status": "VARCHAR", "deployment_target": "VARCHAR",
    "is_champion": "BOOLEAN DEFAULT FALSE", "rolled_back_from": "VARCHAR", "deployed_at": "TIMESTAMP",
}
RETRAIN_COLUMNS = {"dataset_version": "VARCHAR", "label_version": "VARCHAR"}

def migrate():
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in (("model_registry", MODEL_COLUMNS), ("retraining_history", RETRAIN_COLUMNS)):
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, typ in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {typ}"))
    print("MLOps registry migration complete")

if __name__ == "__main__":
    migrate()
