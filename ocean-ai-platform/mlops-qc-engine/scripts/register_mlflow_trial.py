"""Register local trial evidence in SQLite; never promote operational models."""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
for _path_entry in (str(BASE), str(BASE / "scripts")):
    if _path_entry not in sys.path:
        sys.path.insert(0, _path_entry)
sys.modules.setdefault("register_mlflow_trial", sys.modules[__name__])
sys.modules.setdefault("scripts.register_mlflow_trial", sys.modules[__name__])

from scripts.local_trial_manifest import sha256, validate, write_json
from scripts.workspace_paths import resolve_manifest_root

mlflow: Any = importlib.import_module("mlflow")
MlflowClient: Any = importlib.import_module("mlflow.tracking").MlflowClient


def register(manifest_path: Path, runs_root: Path, store: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate(manifest)
    root = resolve_manifest_root(manifest, BASE)
    store = store.resolve()
    if store.is_relative_to(root):
        raise ValueError("Tracking store cannot be inside protected input")
    store.mkdir(parents=True, exist_ok=True)
    (store / "verification").mkdir(exist_ok=True)
    uri = "sqlite:///" + (store / "tracking.db").as_posix()
    client = MlflowClient(tracking_uri=uri, registry_uri=uri)
    name = "OceanDB_AI_LOCAL_TRIAL"
    experiment = client.get_experiment_by_name(name)
    experiment_id = experiment.experiment_id if experiment else client.create_experiment(
        name, artifact_location=(store / "artifacts").as_uri())
    existing_historic = client.search_runs([experiment_id],
        filter_string="tags.`mlflow.runName` = 'IMPORTED_LEGACY_inventory'", max_results=1)
    historic = existing_historic[0] if existing_historic else client.create_run(experiment_id,
        tags={"mlflow.runName": "IMPORTED_LEGACY_inventory", "evidence_level": "IMPORTED_LEGACY",
              "reproducible_training": "false", "operational_deployment": "false", "ai_flag_position": "11"})
    client.log_param(historic.info.run_id, "mapping_pairs", len(manifest["models"]))
    client.log_artifact(historic.info.run_id, str(manifest_path), "evidence")
    client.set_terminated(historic.info.run_id)
    registered_runs, registered_models = [], []
    model_run = None
    for path in sorted(runs_root.glob("*/run.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("status") not in {"FINISHED", "FAILED"} or record.get("manifest_sha256") != sha256(manifest_path):
            continue
        result_path = path.parent / "results.json"
        results = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else None
        previous = client.search_runs([experiment_id],
            filter_string=f"tags.local_wrapper_run_id = '{record['run_id']}'", max_results=1)
        run = previous[0] if previous else client.create_run(experiment_id, tags={"mlflow.runName": record["job"] + "_" + record["run_id"],
            "local_wrapper_run_id": record["run_id"], "evidence_level": results["kind"] if results is not None else "INCOMPLETE_RESULT_FAILED_EXECUTION",
            "database_used": "false", "live_parallel_operation": "false",
            "operational_deployment": "false", "ai_flag_position": "11"})
        run_id = run.info.run_id
        try:
            client.log_param(run_id, "manifest_sha256", record["manifest_sha256"])
            client.log_param(run_id, "model_count", results["model_count"] if results is not None else len(manifest["models"]))
            client.log_param(run_id, "result_report_available", str(results is not None).lower())
            client.log_metric(run_id, "elapsed_seconds", record["elapsed_seconds"])
            for key in ("passed_count", "evaluated_models", "total_samples", "mismatch_or_error_count"):
                if results is not None and key in results:
                    client.log_metric(run_id, key, results[key])
            evidence = [path, path.parent / "results.json", path.parent / "stdout.log", path.parent / "stderr.log"]
            evidence.extend(path.parent.glob("*_investigation.json"))
            for artifact in evidence:
                if artifact.is_file():
                    client.log_artifact(run_id, str(artifact), "evidence")
            client.log_artifact(run_id, str(manifest_path), "evidence")
            if (path.parent / "replay_inputs").is_dir():
                client.log_artifacts(run_id, str(path.parent / "replay_inputs"), "replay_inputs")
            status = "FINISHED" if record["status"] == "FINISHED" and results is not None and results.get("passed") else "FAILED"
            client.set_terminated(run_id, status=status)
        except Exception:
            client.set_terminated(run_id, status="FAILED")
            raise
        registered_runs.append({"wrapper_run_id": record["run_id"], "job": record["job"], "mlflow_run_id": run_id,
                                "status": status})
        if record["job"] == "models" and status == "FINISHED" and results is not None and results["passed_count"] == len(manifest["models"]):
            model_run = run_id
    if model_run is None:
        raise ValueError("No completed all-model test for registry trial")
    for pair in manifest["models"]:
        model_name = f"LOCAL_TRIAL_{pair['station']}_{pair['sensor']}"
        matches = client.search_registered_models(filter_string=f"name = '{model_name}'")
        if not matches:
            client.create_registered_model(model_name, tags={"scope": "LOCAL_TRIAL_ONLY", "operational_deployment": "false"})
        artifact_path = f"model_assets/{pair['station']}/{pair['sensor']}"
        for role in ("model", "scaler", "threshold"):
            client.log_artifact(model_run, str(root / pair[role]), artifact_path)
        source = client.get_run(model_run).info.artifact_uri + "/" + artifact_path
        versions = client.search_model_versions(filter_string=f"name = '{model_name}' AND run_id = '{model_run}'")
        version = versions[0] if versions else client.create_model_version(model_name, source=source, run_id=model_run,
            tags={"evidence_level": "CPU_FIXED_INPUT_ONLY", "source_model_sha256": sha256(root / pair["model"]),
                  "not_a_deployable_mlflow_flavor": "true"})
        if version.status != "READY":
            raise ValueError(f"Model version not ready: {model_name}")
        client.set_registered_model_alias(model_name, "trial", version.version)
        loaded = client.get_model_version_by_alias(model_name, "trial")
        if loaded.version != version.version or loaded.run_id != model_run:
            raise ValueError("Registry read-back mismatch")
        for role in ("model", "scaler", "threshold"):
            downloaded = Path(client.download_artifacts(model_run, artifact_path + "/" + Path(pair[role]).name,
                                                        dst_path=str(store / "verification")))
            if sha256(downloaded) != sha256(root / pair[role]):
                raise ValueError(f"Downloaded {role} artifact hash mismatch")
        registered_models.append({"name": model_name, "version": version.version, "alias": "trial",
                                  "source": source, "artifact_hash_verified": True})
    result = {"passed": True, "mlflow_version": mlflow.__version__, "tracking_uri": uri,
              "experiment_id": experiment_id, "historical_run_id": historic.info.run_id,
              "runs": registered_runs, "models": registered_models, "operational_deployment": False,
              "registry_scope": "LOCAL_RAW_H5_ASSETS_NOT_DEPLOYABLE_MLFLOW_FLAVOR",
              "verified_at_unix": time.time(), "inputs_after": validate(manifest)}
    write_json(store / "registration_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = register(args.manifest.resolve(), args.runs_root.resolve(), args.store)
    except Exception as error:
        write_json(args.store / f"registration_failure_{time.time_ns()}.json",
                   {"passed": False, "error": f"{type(error).__name__}: {error}"})
        raise
    print(json.dumps({"passed": result["passed"], "runs": len(result["runs"]), "models": len(result["models"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
