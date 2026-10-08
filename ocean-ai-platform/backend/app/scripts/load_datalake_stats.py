# 파일 역할: 원시 관측 전체 대신 Data Lake 집계 통계를 DB에 적재합니다.
"""Load Parquet manifest statistics into PostgreSQL without loading observations."""
import argparse, hashlib, json
from pathlib import Path
from app.core.database import SessionLocal, Base, engine
from app.models.domain import DataLakeStat

def load(manifest: Path, lake_name: str):
    payload=json.loads(manifest.read_text(encoding="utf-8")); manifest_hash=hashlib.sha256(manifest.read_bytes()).hexdigest()
    Base.metadata.create_all(bind=engine); db=SessionLocal(); inserted=0
    try:
        # Keep the load repeatable when a manifest is rebuilt.
        db.query(DataLakeStat).filter(
            DataLakeStat.lake_name == lake_name,
            DataLakeStat.partition_path == str(manifest.parent),
        ).delete(synchronize_session=False)
        for variable, stat in payload.get("stats", {}).items():
            row=DataLakeStat(lake_name=lake_name, partition_path=str(manifest.parent), variable_code=variable, row_count=int(stat.get("rows",0)), missing_count=int(stat.get("missing",0)), min_value=stat.get("min"), max_value=stat.get("max"), mean_value=stat.get("mean"), manifest_hash=manifest_hash)
            db.add(row); inserted += 1
        db.commit(); return inserted
    finally: db.close()

if __name__ == "__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--manifest", type=Path, required=True); ap.add_argument("--lake-name", required=True); a=ap.parse_args(); print({"inserted":load(a.manifest,a.lake_name)})
