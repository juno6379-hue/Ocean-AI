# 파일 역할: 과거 Parquet 시계열을 사용한 모델 학습을 실행합니다.
"""Stream an explicit wide historical Parquet source into QC-filtered hourly training.

This adapter deliberately requires column names instead of trusting legacy
partition labels, which can contain mixed source variables or processing stages.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from app.ml.trainer import train_from_hourly
from app.ml.model_registry import save_candidate


def hourly_from_parquet(source: Path, time_column: str, value_column: str, qc_column: str, source_timezone="Asia/Seoul", min_samples=30):
    parquet = pq.ParquetFile(source)
    columns = [time_column, value_column, qc_column]
    if not set(columns) <= set(parquet.schema_arrow.names):
        raise ValueError("Explicit time, value and QC columns are required")
    parts, total, accepted, rejected, invalid_times = [], 0, 0, 0, 0
    last_timestamp = None
    first_timestamp = None
    qc_counts = {}
    for batch in parquet.iter_batches(batch_size=200000, columns=columns):
        frame = batch.to_pandas()
        total += len(frame)
        times = pd.to_datetime(frame[time_column], errors="coerce")
        invalid_times += int(times.isna().sum())
        times = times.dt.tz_localize(source_timezone) if times.dt.tz is None else times
        times = times.dt.tz_convert("UTC")
        finite_times = times.dropna()
        if not finite_times.is_monotonic_increasing or finite_times.duplicated().any():
            raise ValueError("Historical timestamps must be ordered and unique")
        if len(finite_times):
            if last_timestamp is not None and finite_times.iloc[0] <= last_timestamp:
                raise ValueError("Timestamp overlap across Parquet batches requires review")
            first_timestamp = first_timestamp if first_timestamp is not None else finite_times.iloc[0]
            last_timestamp = finite_times.iloc[-1]
        values = pd.to_numeric(frame[value_column], errors="coerce")
        qc = frame[qc_column].fillna("MISSING").astype(str).str.strip().str.upper()
        for flag, count in qc.value_counts().items():
            qc_counts[flag] = qc_counts.get(flag, 0) + int(count)
        valid = times.notna() & np.isfinite(values) & qc.isin(["G", "1", "GOOD"])
        accepted += int(valid.sum())
        rejected += int((~valid).sum())
        grouped = pd.DataFrame({"end": times[valid].dt.floor("h") + pd.Timedelta(hours=1), "value": values[valid]})
        parts.append(grouped.groupby("end").value.agg(["sum", "count"]))
    if not parts or first_timestamp is None:
        raise ValueError("No usable historical observations")
    combined = pd.concat(parts).groupby(level=0).sum()
    hourly = (combined["sum"] / combined["count"]).where(combined["count"] >= min_samples)
    index = pd.date_range(first_timestamp.floor("h") + pd.Timedelta(hours=1), last_timestamp.floor("h") + pd.Timedelta(hours=1), freq="h")
    hourly = hourly.reindex(index).rename("target")
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    quality = {"source_rows": total, "accepted_rows": accepted, "rejected_or_missing_rows": rejected,
               "invalid_timestamps": invalid_times, "qc_counts": qc_counts, "accepted_qc": ["G", "1", "GOOD"],
               "total_hour_bins": len(hourly), "usable_hour_bins": int(hourly.notna().sum()),
               "min_samples_per_hour": min_samples, "missing_bins_interpolated": 0,
               "source_timezone": source_timezone, "source_sha256": digest.hexdigest(),
               "source_first_utc": first_timestamp.isoformat(), "source_last_utc": last_timestamp.isoformat(),
               "source_columns": columns, "preprocessing_version": f"PARQUET-QC-GOOD-HOURLY-MIN{min_samples}-1"}
    return hourly, quality


def train(source, output, station, time_column, value_column, qc_column, unit):
    if output.exists():
        raise ValueError("Use a new output directory")
    hourly, quality = hourly_from_parquet(source, time_column, value_column, qc_column)
    output.mkdir(parents=True)
    hourly.to_frame().to_parquet(output / "hourly.parquet")
    print(json.dumps({"stage": "historical_parquet", **quality}), flush=True)
    model, metrics, evaluation, features = train_from_hourly(hourly, quality)
    metrics.update({"station_id": station, "variable_code": "TIDE", "unit": unit,
                    "source_kind": "EXISTING_PARQUET", "source_file": source.name,
                    "label_version": "SOURCE_QC_GOOD", "source_qc_available": True})
    result = save_candidate(model, metrics, evaluation, features, output / "candidate")
    print(json.dumps({"stage": "historical_training", "test": result["test_metrics"], "persistence": result["baseline_persistence"],
                      "mae_improvement_pct": result["mae_improvement_vs_persistence_pct"]}), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--station-id", required=True)
    parser.add_argument("--time-column", default="Time")
    parser.add_argument("--value-column", default="OTT")
    parser.add_argument("--qc-column", default="QC2")
    parser.add_argument("--unit", default="cm")
    args = parser.parse_args()
    train(args.source, args.output, args.station_id, args.time_column, args.value_column, args.qc_column, args.unit)
