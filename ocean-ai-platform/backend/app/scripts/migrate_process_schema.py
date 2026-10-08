# 파일 역할: 관측 처리 계층의 스키마와 인덱스를 갱신합니다.
"""process.md P0/P1 확장 컬럼을 기존 DB에 반영한다."""
from sqlalchemy import inspect, text
from app.core.database import Base, engine
import app.models.domain

COLUMNS = {
    "ai_label": {"review_comment": "TEXT"},
    "document_index": {"parser_version": "VARCHAR"},
    "feature_definition": {"created_at": "TIMESTAMP"},
    "feature_value": {"observation_id": "VARCHAR"},
    "observation_raw": {"qc_flag": "VARCHAR", "mqc_flag": "VARCHAR", "water_step": "DOUBLE PRECISION", "from_depth": "DOUBLE PRECISION", "to_depth": "DOUBLE PRECISION", "receive_time": "TIMESTAMP", "source_item_code": "VARCHAR"},
    "observation_standard": {"qc_flag": "VARCHAR", "mqc_flag": "VARCHAR", "water_step": "DOUBLE PRECISION", "from_depth": "DOUBLE PRECISION", "to_depth": "DOUBLE PRECISION", "receive_time": "TIMESTAMP", "source_item_code": "VARCHAR"},
    "model_registry": {"target_task":"VARCHAR", "deployment_stage":"VARCHAR", "latency_ms":"DOUBLE PRECISION"},
    "dataset_registry": {"sensor_scope":"JSON", "qc_rule_version":"VARCHAR", "data_hash":"VARCHAR", "status":"VARCHAR", "created_by":"VARCHAR", "approved_by":"VARCHAR"},
}

def migrate():
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, additions in COLUMNS.items():
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, typ in additions.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {typ}"))
        conn.execute(text("DELETE FROM observation_raw a USING observation_raw b WHERE a.id>b.id AND a.station_id=b.station_id AND a.sensor_id=b.sensor_id AND a.variable_code=b.variable_code AND a.timestamp_utc=b.timestamp_utc"))
        conn.execute(text("DELETE FROM observation_standard a USING observation_standard b WHERE a.ctid>b.ctid AND a.station_id=b.station_id AND a.sensor_id=b.sensor_id AND a.variable_code=b.variable_code AND a.timestamp_utc=b.timestamp_utc"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_observation_raw_natural_key_idx ON observation_raw (station_id, sensor_id, variable_code, timestamp_utc)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_observation_standard_natural_key_idx ON observation_standard (station_id, sensor_id, variable_code, timestamp_utc)"))
    print("process schema migration complete")

if __name__ == "__main__":
    migrate()
