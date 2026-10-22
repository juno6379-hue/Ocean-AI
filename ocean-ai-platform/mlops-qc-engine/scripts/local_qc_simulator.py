"""Offline whole-QC comparison CLI. Never connects to a database or promotes models."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import logging
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

pd: Any = importlib.import_module("pandas")


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _period(snapshot_id, dataset_id, scope, start_time, end_time, base):
    if scope not in ("TEST", "ALL"):
        raise ValueError("scope는 TEST 또는 ALL이어야 합니다.")
    if bool(start_time) != bool(end_time):
        raise ValueError("시작과 종료 시각을 함께 지정해 주세요.")
    if start_time:
        return pd.Timestamp(start_time), pd.Timestamp(end_time)
    if snapshot_id:
        from scripts.ocean_ai_snapshot import ParquetSnapshotAuthority
        authority = ParquetSnapshotAuthority(root=base / "reports/ocean_ai_snapshots",
                                             preview_output=base / "reports/dataset_previews")
        manifest = _json(base / "reports/ocean_ai_snapshots" / snapshot_id / "snapshot_manifest.json")
        if scope == "TEST":
            intervals = authority.split_target_intervals(snapshot_id, "TEST", manifest=manifest)
            if len(intervals) != 1:
                raise ValueError("현재 CLI의 자동 TEST 범위는 단일 시간순 holdout만 지원합니다. 명시적 구간을 지정해 주세요.")
            return pd.Timestamp(intervals[0][0]), pd.Timestamp(intervals[0][1]) - pd.Timedelta(minutes=1)
    elif dataset_id:
        if scope == "TEST":
            raise ValueError("dataset_id의 TEST 범위는 시작·종료 시각을 명시해야 합니다.")
        manifest = _json(base / "reports/dataset_previews" / dataset_id / "dataset_manifest.json")
    else:
        raise ValueError("snapshot_id 또는 dataset_id가 필요합니다.")
    end = str(manifest["date_end"])
    return pd.Timestamp(manifest["date_start"]), (pd.Timestamp(end) + pd.Timedelta(days=1, minutes=-1)
                                                 if len(end) <= 10 else pd.Timestamp(end))


def simulate(candidate_run_id, *, snapshot_id=None, dataset_id=None, scope="TEST",
             start_time=None, end_time=None, warmup_minutes=180, output_root=None,
             simulation_id=None, optimize=True, base=BASE) -> dict:
    from scripts.local_qc.bundle_loader import load_candidate_bundle, load_champion_bundle
    from scripts.local_qc.data_source import load_source
    from scripts.local_qc.evaluation import evaluate_replay, evaluate_tier1
    from scripts.local_qc.replay import ReplayEngine, json_value
    from scripts.evaluation_safety import TIERED_PROMOTION_POLICY, local_qc_promotion_verdict

    base = Path(base).resolve()
    candidate = load_candidate_bundle(candidate_run_id, base=base)
    champion = load_champion_bundle(candidate.station, candidate.sensor, base=base)
    if not snapshot_id and not dataset_id:
        artifact = _json(base / "reports/candidate_runs" / candidate_run_id / "artifact.json")
        snapshot_id = artifact["snapshot_id"]
    start, end = _period(snapshot_id, dataset_id, scope, start_time, end_time, base)
    stream = load_source(snapshot_id=snapshot_id, dataset_id=dataset_id,
        station=candidate.station, sensor=candidate.sensor, start_time=start, end_time=end,
        warmup_minutes=warmup_minutes, base=base)
    sim_id = simulation_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:8]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", sim_id):
        raise ValueError("simulation_id 형식이 올바르지 않습니다.")
    folder = Path(output_root or base / "reports/local_qc_simulations") / sim_id
    folder.mkdir(parents=True, exist_ok=False)
    points = list(stream.iter_points())
    source_metadata = dict(stream.metadata)
    warmup_points = [point for point in points if point["timestamp"] < start]
    evaluated_points = [point for point in points if point["timestamp"] >= start]
    source_metadata.update({
        "warmup_observed_minutes": sum(pd.notna(point["OBS"]) for point in warmup_points),
        "warmup_missing_observation_minutes": sum(pd.isna(point["OBS"]) for point in warmup_points),
        "raw_input_coverage": {
            "scoped_minutes": len(evaluated_points),
            "missing_observation_minutes": sum(pd.isna(point["OBS"]) for point in evaluated_points),
            "missing_prediction_minutes": sum(pd.isna(point["TIDE_PRE_VAL"]) for point in evaluated_points),
            "definition": "Post-warmup raw input missingness, independent of retrospective QC flags."}})
    started = time.perf_counter()
    engines, replay_models, performance = {}, {}, {}
    for bundle in (champion, candidate):
        print(f"QC_START {bundle.role} {len(points)} minutes", flush=True)
        engine = ReplayEngine(bundle, optimize=optimize, start_time=start, end_time=end)
        began = time.perf_counter()
        if not optimize:
            engine.prepare(points)
        replay_models[bundle.role] = engine.run(points)
        engines[bundle.role] = engine
        performance[bundle.role] = {"elapsed_seconds": time.perf_counter() - began,
            "raw_cache_hits": engine.predictor.hits, "single_inference_calls": engine.predictor.single_calls,
            "precompute_calls": engine.predictor.precompute_calls,
            "precompute_microbatch_size": 1, "optimization_enabled": bool(optimize)}
        print(f"QC_DONE {bundle.role} {performance[bundle.role]['elapsed_seconds']:.2f}s", flush=True)
    replay = {"station": candidate.station, "sensor": candidate.sensor, "start_time": str(start),
              "end_time": str(end), "metadata": source_metadata, "models": replay_models}
    tier2 = evaluate_replay(replay, stream.labels, source_metadata=source_metadata)
    times = [point["timestamp"] for point in points]
    common = []
    for index, point in enumerate(points):
        prior = points[max(0, index - 4):index]
        common.append(index >= 4 and point["timestamp"] >= start and
            pd.notna(point["OBS"]) and pd.notna(point["TIDE_PRE_VAL"]) and
            all(stream.labels.get(item["timestamp"]) == "G" and pd.notna(item["OBS"])
                and pd.notna(item["TIDE_PRE_VAL"]) for item in prior))
    predictions = {name: [engine.raw_predictions.get(timestamp) for timestamp in times]
                   for name, engine in engines.items()}
    tier1 = evaluate_tier1(times, [point["OBS"] for point in points],
        [point["TIDE_PRE_VAL"] for point in points], predictions,
        {bundle.role: bundle.effective_lstm_threshold_cm for bundle in (champion, candidate)},
        stream.labels, common_mask=common)
    files = {}
    for name, result in replay_models.items():
        path = folder / f"{name}.csv"
        keys = list(dict.fromkeys(key for row in result["rows"] for key in row)) + ["MQC_FLAG"]
        with path.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=keys)
            writer.writeheader()
            for row in result["rows"]:
                writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                                 for key, value in {**row, "MQC_FLAG": stream.labels.get(pd.Timestamp(row["timestamp"]))}.items()})
        files[name + "_csv"] = {"path": str(path), "sha256": _sha(path)}
    series = {"schema_version": "local-qc-series-1", "timestamps": [str(timestamp) for timestamp in times],
        "real_obs": [point["OBS"] for point in points], "tide_pre_val": [point["TIDE_PRE_VAL"] for point in points],
        "labels": [stream.labels.get(timestamp) for timestamp in times], "common_tier1_mask": common,
        "tier1_predictions": predictions,
        "models": {name: {key: [row.get(key) for row in result["rows"]] for key in (
            "predicted_obs", "online_flag", "online_source", "consolidated_flag", "consolidated_source",
            "interpolate_count", "last_residual_applied", "retroactive_changes")}
            for name, result in replay_models.items()}}
    path = folder / "series.json"
    path.write_text(json.dumps(json_value(series), ensure_ascii=False, allow_nan=False), encoding="utf-8")
    files["series"] = {"path": str(path), "sha256": _sha(path)}
    comparison = {"schema_version": "local-qc-comparison-1", "simulation_id": sim_id,
        "policy_version": TIERED_PROMOTION_POLICY,
        "candidate_run_id": candidate_run_id, "station": candidate.station, "sensor": candidate.sensor,
        "evaluated_snapshot_id": snapshot_id, "dataset_id": dataset_id, "scope": scope,
        "start_time": str(start), "end_time": str(end), "warmup_minutes": warmup_minutes,
        "source_metadata": source_metadata,
        "bundle_metadata": {bundle.role: bundle.metadata for bundle in (champion, candidate)},
        "tier1": tier1, "tier2": tier2, "prediction_optimization": performance,
        "elapsed_seconds": time.perf_counter() - started, "files": files,
        "operational_database_used": False, "operational_assets_modified": False}
    comparison["promotion_verdict"] = local_qc_promotion_verdict(comparison)
    comparison["promotion_allowed"] = comparison["promotion_verdict"]["promotion_allowed"]
    comparison = json_value(comparison)
    path = folder / "comparison.json"
    path.write_text(json.dumps(comparison, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    receipt = {"simulation_id": sim_id, "comparison": str(path), "comparison_sha256": _sha(path)}
    (folder / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return comparison


run_local_qc_simulation = simulate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-run-id", required=True)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--snapshot-id")
    source.add_argument("--dataset-id")
    parser.add_argument("--scope", choices=("TEST", "ALL"), default="TEST")
    parser.add_argument("--start-time")
    parser.add_argument("--end-time")
    parser.add_argument("--warmup-minutes", type=int, default=180)
    parser.add_argument("--output-root")
    parser.add_argument("--simulation-id")
    parser.add_argument("--single-inference", action="store_true")
    args = parser.parse_args(argv)
    logging.getLogger().setLevel(logging.ERROR)
    values = vars(args)
    values["optimize"] = not values.pop("single_inference")
    result = simulate(**values)
    print(json.dumps({"simulation_id": result["simulation_id"], "files": result["files"],
                      "elapsed_seconds": result["elapsed_seconds"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
