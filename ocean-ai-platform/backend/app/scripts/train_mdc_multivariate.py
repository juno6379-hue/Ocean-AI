# 파일 역할: MDC 관측자료 기반 다변량 모델 학습을 실행합니다.
"""Train same-station covariates from verified PostgreSQL extraction snapshots.

Each input directory must contain validate_live_pipeline's report and Parquet.
Station identity and snapshot digests are checked before any series are joined.
"""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
from app.ml.feature_generator import prepare_hourly
from app.ml.trainer import train_from_hourly
from app.ml.model_registry import save_candidate


def read_verified(run):
    report = json.loads((run / "verification.json").read_text(encoding="utf-8"))
    snapshot = run / "postgres_observations.parquet"
    if report["status"] != "VERIFIED_CANDIDATE_ONLY" or hashlib.sha256(snapshot.read_bytes()).hexdigest() != report["snapshot_sha256"]:
        raise ValueError("Input snapshot has not been verified or has changed")
    hourly, quality = prepare_hourly(pd.read_parquet(snapshot))
    return report, hourly, quality


def train(target_run, covariate_run, output):
    target, hourly, quality = read_verified(target_run)
    external, covariate, _ = read_verified(covariate_run)
    if target["station_id"] != external["station_id"]:
        raise ValueError("Cross-station joins require an explicit station mapping")
    variable = external["postgres"]["standard_variable"]
    quality["source_snapshots"] = [target["snapshot_sha256"], external["snapshot_sha256"]]
    model, metrics, evaluation, features = train_from_hourly(hourly, quality, external_hourly=covariate.to_frame(variable))
    metrics.update({"station_id": target["station_id"], "variable_code": target["postgres"]["standard_variable"],
                    "unit": target["postgres"]["unit"], "covariates": [variable],
                    "feature_version": "HOURLY-LAGS-SAME-STATION-EXTERNAL-1",
                    "source_kind": "VERIFIED_MDC_POSTGRES_SNAPSHOTS", "source_qc_available": False})
    result = save_candidate(model, metrics, evaluation, features, output)
    print(json.dumps({"test": result["test_metrics"], "persistence": result["baseline_persistence"],
                      "station_id": result["station_id"], "covariates": result["covariates"]}), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-run", type=Path, required=True)
    parser.add_argument("--covariate-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    train(args.target_run, args.covariate_run, args.output)
