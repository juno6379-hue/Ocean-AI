# 파일 역할: 실자료 처리 경로와 연결 상태를 검증합니다.
"""Verify Oracle -> PostgreSQL -> offline training without changing production rows.

Oracle transactions are read-only. PostgreSQL DDL/data/registry writes use an
isolated schema inside an outer transaction that is always rolled back. ORM
commits release savepoints only. Raw data and model artifacts remain local.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import uuid
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import Base
from app.models.domain import StationMetadata, ObservationRaw, ObservationStandard, ModelRegistry
from app.scripts.sync_mdc_db import (init_oracle, fetch_with_fallback, observation_from_mdc,
    insert_observations_idempotent, insert_standardized_idempotent)
from app.ml.trainer import train_hourly_forecaster
from app.ml.model_registry import save_candidate
from app.api.routes_mlops import register_model, ModelRegistrationRequest


def validate(station: str, item: str, start: dt.datetime, end: dt.datetime, output: Path, limit=120000, table="WEB_OBS_ST"):
    if table not in {"WEB_OBS_ST", "TP_OBS_SO"}:
        raise ValueError("Unsupported source table")
    if output.exists():
        raise ValueError("Use a new output directory for each validation run")
    if start >= end or limit < 1000 or limit > 200000:
        raise ValueError("Invalid time range or row limit (1000..200000)")
    output.mkdir(parents=True)
    report = {"started_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "station_id": station,
              "source_item_code": item, "source_table": table, "oracle_read_only": True, "production_rows_modified": False,
              "source_period_kst": {"start": start.isoformat(), "end_exclusive": end.isoformat()}}
    init_oracle()
    source = f" FROM {table} WHERE OBS_POST_ID=:station AND OBS_ITEM_CODE=:item AND OBS_TIME>=:start_time AND OBS_TIME<:end_time ORDER BY OBS_TIME"
    columns = "OBS_POST_ID, OBS_ITEM_CODE, OBS_TIME, OBS_VALUE"
    # A hard row cap prevents an accidental whole-archive download.
    primary = f"SELECT * FROM (SELECT {columns}, QC_FLAG, MQC_FLAG, RECEIVE_TIME{source}) WHERE ROWNUM <= :row_limit"
    fallback = f"SELECT * FROM (SELECT {columns}{source}) WHERE ROWNUM <= :row_limit"
    rows = fetch_with_fallback(primary, fallback, {"station": station, "item": item, "start_time": start, "end_time": end, "row_limit": limit + 1})
    if not rows or len(rows) > limit:
        raise ValueError(f"Source returned no data or exceeds row limit: {len(rows)}")
    report["oracle"] = {"connected": True, "rows": len(rows), "first_kst": rows[0]["obs_time"].isoformat(),
                        "last_kst": rows[-1]["obs_time"].isoformat(), "qc_available": any(r.get("qc_flag") is not None or r.get("mqc_flag") is not None for r in rows)}
    print(json.dumps({"stage": "oracle_read", **report["oracle"]}), flush=True)
    observations = [observation_from_mdc(row, table) for row in rows]
    engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 10}, pool_pre_ping=True)
    if engine.dialect.name != "postgresql":
        raise ValueError("This verification requires a real PostgreSQL database")
    schema = "validation_" + uuid.uuid4().hex
    with engine.connect() as connection:
        outer = connection.begin()
        try:
            connection.execute(text("SET LOCAL statement_timeout = '60s'"))
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
            Base.metadata.create_all(connection, checkfirst=False)
            with Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False) as db:
                db.add(StationMetadata(station_id=station, station_name=station, status="VALIDATION"))
                db.commit()
                inserted_raw = inserted_standard = 0
                for offset in range(0, len(observations), 1000):
                    batch = observations[offset:offset + 1000]
                    inserted_raw += insert_observations_idempotent(db, batch)
                    inserted_standard += insert_standardized_idempotent(db, batch)
                repeat_raw = insert_observations_idempotent(db, observations[:1000])
                repeat_standard = insert_standardized_idempotent(db, observations[:1000])
                if repeat_raw or repeat_standard:
                    raise AssertionError("Duplicate ingestion changed row counts")
                raw_count, standard_count = db.query(ObservationRaw).count(), db.query(ObservationStandard).count()
                expected = len({(o.station_id, o.sensor_id, o.variable_code, o.timestamp_utc) for o in observations})
                if raw_count != expected or standard_count != expected:
                    raise AssertionError("Oracle/PostgreSQL row counts differ")
                stored = db.query(ObservationStandard).order_by(ObservationStandard.timestamp_utc).all()
                source_values = {o.timestamp_utc: o.value_raw for o in observations}
                if any(row.value_standard != source_values[row.timestamp_utc] for row in stored):
                    raise AssertionError("Round-trip observation values differ")
                frame = pd.DataFrame([{"timestamp_utc": row.timestamp_utc, "value_raw": row.value_standard} for row in stored])
                frame.to_parquet(output / "postgres_observations.parquet", index=False)
                report["postgres"] = {"connected": True, "schema_isolated": True, "raw_rows": raw_count, "standard_rows": standard_count,
                    "first_insert_raw": inserted_raw, "first_insert_standard": inserted_standard, "repeat_insert_raw": repeat_raw,
                    "repeat_insert_standard": repeat_standard, "source_values_match": True,
                    "source_timestamp_preserved": stored[0].timestamp_utc == rows[0]["obs_time"] - dt.timedelta(hours=9),
                    "standard_variable": stored[0].variable_code, "unit": stored[0].standard_unit}
                print(json.dumps({"stage": "postgres_roundtrip", **report["postgres"]}), flush=True)
                model, metadata, evaluation, features = train_hourly_forecaster(frame)
                metadata.update({"station_id": station, "variable_code": stored[0].variable_code, "unit": stored[0].standard_unit,
                                 "source_table": table, "source_qc_available": report["oracle"]["qc_available"]})
                metadata = save_candidate(model, metadata, evaluation, features, output / "candidate")
                registration = ModelRegistrationRequest(model_name=metadata["model_name"], model_type="RIDGE",
                    model_version="RIDGE-" + output.name, target_variable=stored[0].variable_code, target_task="FORECASTING",
                    dataset_version=metadata["dataset_hash"], feature_version=metadata["feature_version"],
                    label_version=metadata["label_version"], preprocessing_version=metadata["preprocessing_version"],
                    metrics={**metadata["test_metrics"], "latency": metadata["latency_ms_per_sample"]},
                    artifact_path=str((output / "candidate" / "model.joblib").resolve()))
                registered = register_model(registration, db)
                candidate = db.query(ModelRegistry).one()
                if candidate.status != "PENDING_APPROVAL" or candidate.is_champion:
                    raise AssertionError("Training unexpectedly promoted a model")
                report["registry"] = {"roundtrip_verified": True, "persisted_to_production": False, "status": registered["status"]}
                report["training"] = metadata
        finally:
            outer.rollback()
    with engine.connect() as connection:
        report["postgres_schema_removed"] = connection.execute(text("SELECT to_regnamespace(:schema) IS NULL"), {"schema": schema}).scalar()
    engine.dispose()
    if not report["postgres_schema_removed"]:
        raise AssertionError("Validation schema cleanup failed")
    report["snapshot_sha256"] = hashlib.sha256((output / "postgres_observations.parquet").read_bytes()).hexdigest()
    report["completed_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    report["status"] = "VERIFIED_CANDIDATE_ONLY"
    (output / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", choices=["WEB_OBS_ST", "TP_OBS_SO"], default="WEB_OBS_ST")
    parser.add_argument("--station-id", required=True)
    parser.add_argument("--item", required=True)
    parser.add_argument("--start", required=True, type=dt.datetime.fromisoformat)
    parser.add_argument("--end", required=True, type=dt.datetime.fromisoformat)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = validate(args.station_id, args.item, args.start, args.end, args.output, table=args.table)
    print(json.dumps({"status": result["status"], "test_metrics": result["training"]["test_metrics"],
                      "persistence": result["training"]["baseline_persistence"], "schema_removed": result["postgres_schema_removed"]}, ensure_ascii=False))
