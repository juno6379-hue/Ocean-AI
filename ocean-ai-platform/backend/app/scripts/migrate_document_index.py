# 파일 역할: 기존 문서 색인 테이블의 확장 컬럼을 반영합니다.
"""DocumentIndex 확장 컬럼을 기존 PostgreSQL 테이블에 반영한다."""
from sqlalchemy import inspect, text
from app.core.database import engine

MISSING_COLUMNS = {
    "document_id": "VARCHAR(128)",
    "report_id": "VARCHAR(128)",
    "chunk_id": "VARCHAR(128)",
    "period_start": "TIMESTAMP",
    "period_end": "TIMESTAMP",
    "related_sensor_id": "VARCHAR",
    "event_id": "VARCHAR",
    "event_type": "VARCHAR",
    "error_type": "VARCHAR",
    "error_cause": "VARCHAR",
    "section_name": "VARCHAR",
    "page_no": "INTEGER",
    "embedding_model": "VARCHAR",
    "embedding_version": "VARCHAR",
}


def migrate():
    inspector = inspect(engine)
    existing = {column["name"] for column in inspector.get_columns("document_index")}
    with engine.begin() as conn:
        for name, data_type in MISSING_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE document_index ADD COLUMN {name} {data_type}"))
    print("DocumentIndex migration complete")


if __name__ == "__main__":
    migrate()
