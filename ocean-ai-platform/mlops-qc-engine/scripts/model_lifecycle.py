"""Candidate training orchestration, MLflow registration, promotion (champion), and rollback lifecycle."""
from __future__ import annotations

import contextlib
import hashlib
import importlib
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
for _path_entry in (str(BASE), str(BASE / "scripts")):
    if _path_entry not in sys.path:
        sys.path.insert(0, _path_entry)
sys.modules.setdefault("model_lifecycle", sys.modules[__name__])
sys.modules.setdefault("scripts.model_lifecycle", sys.modules[__name__])

from scripts.local_trial_manifest import confined_path, read_json, sha256, validate, write_json
from scripts.ocean_ai_snapshot import ParquetSnapshotAuthority
from scripts.workspace_paths import resolve_manifest_root, resolve_project_path
from scripts.tensorflow_runtime import resolve_tensorflow_python
from scripts.evaluation_safety import TIERED_PROMOTION_POLICY, honest_promotion_verdict, local_qc_promotion_verdict
from scripts.training_control import DEFAULT_BATCH_SIZE, DEFAULT_EPOCHS
from scripts.comparison_contract import DUEL_MODEL_KEYS, duel_comparison, duel_series

MANIFEST = BASE / "manifests/20261006_local_trial_manifest.json"
RELEASES_DIR = BASE / "manifests/releases"
ACTIVE_POINTER_PATH = BASE / "manifests/active_release_pointer.json"
DEPLOYMENTS_DIR = BASE / "reports/deployments"
CANDIDATE_RUNS_ROOT = BASE / "reports/candidate_runs"
CANDIDATE_JOBS_ROOT = BASE / "reports/candidate_jobs"
LOCAL_QC_SIMULATIONS_ROOT = BASE / "reports/local_qc_simulations"
STORE = BASE / "reports/mlflow_trial"
TF_PYTHON = resolve_tensorflow_python(BASE)
RELEASE_SCHEMA_PATH = BASE / "schemas/operational_release_manifest.schema.json"

SEA_CODE_MAP = {
    "동해": "EAST",
    "서해": "WEST",
    "남해": "SOUTH",
}


class WorkerExecutionError(RuntimeError):
    """A failed child process with the run identity retained by its parent."""

    def __init__(self, message: str, run_id: str, run_folder: Path,
                 exit_code: int | None, timed_out: bool = False):
        self.candidate_run_id = run_id
        self.worker_exit_code = exit_code
        self.worker_exit_code_hex = f"0x{exit_code & 0xFFFFFFFF:08X}" if exit_code is not None else None
        self.stdout_path = str(run_folder / "stdout.log")
        self.stderr_path = str(run_folder / "stderr.log")
        self.diagnostics_path = str(run_folder / "training_diagnostics.json")
        self.failure_stage = "worker_start"
        self.timed_out = timed_out
        self.diagnostics_error = None
        self.failure_recording_error: str | None = None
        diagnostic_file = Path(self.diagnostics_path)
        if diagnostic_file.is_file():
            try:
                diagnostic = read_json(diagnostic_file)
                self.failure_stage = str(diagnostic.get("last_stage") or "unknown")
            except (OSError, ValueError, TypeError) as exc:
                self.failure_stage = "unknown"
                self.diagnostics_error = f"{type(exc).__name__}: {exc}"
        super().__init__(message)

    def as_dict(self) -> dict:
        return {key: getattr(self, key) for key in (
            "candidate_run_id", "worker_exit_code", "worker_exit_code_hex", "failure_stage",
            "stdout_path", "stderr_path", "diagnostics_path", "timed_out", "diagnostics_error",
            "failure_recording_error",
        )}


def _record_worker_failure(error: WorkerExecutionError, run_folder: Path) -> None:
    """Keep the parent outcome authoritative even after a child published an artifact."""
    recording_errors = []
    failure_path = run_folder / "worker_failure.json"
    record = {"schema_version": "candidate-worker-failure-1", "status": "FAILED",
              "failed_at": datetime.now(timezone.utc).isoformat(), **error.as_dict()}
    try:
        write_json(failure_path, record)
    except (OSError, ValueError, TypeError) as exc:
        recording_errors.append(f"worker_failure.json: {type(exc).__name__}: {exc}")
        error.failure_recording_error = "; ".join(recording_errors)
    artifact_path = run_folder / "artifact.json"
    if artifact_path.is_file():
        try:
            artifact = read_json(artifact_path)
            artifact.update(status="FAILED", worker_failure=error.as_dict())
            write_json(artifact_path, artifact)
        except (OSError, ValueError, TypeError) as exc:
            recording_errors.append(f"artifact.json: {type(exc).__name__}: {exc}")
    if recording_errors:
        error.failure_recording_error = "; ".join(recording_errors)


def _period_months(start: str, end: str) -> list[str]:
    if not start or not end:
        return []
    first = datetime.strptime(str(start)[:10], "%Y-%m-%d")
    last = datetime.strptime(str(end)[:10], "%Y-%m-%d")
    if first > last:
        raise ValueError("학습 기간의 시작일이 종료일보다 늦습니다.")
    cursor = first.replace(day=1)
    result = []
    while cursor <= last:
        result.append(cursor.strftime("%Y%m"))
        cursor = cursor.replace(year=cursor.year + 1, month=1) if cursor.month == 12 else cursor.replace(month=cursor.month + 1)
    return result


def candidate_training_periods(artifact: dict) -> dict:
    """Expose months used by training or threshold calibration without reading Parquet."""
    snapshot_doc = {}
    snapshot_id = str(artifact.get("snapshot_id") or "")
    snapshot_path = BASE / "reports/ocean_ai_snapshots" / snapshot_id / "snapshot_manifest.json"
    if snapshot_id and snapshot_path.is_file():
        snapshot_doc = read_json(snapshot_path)
    start = artifact.get("train_date_start") or snapshot_doc.get("date_start")
    end = artifact.get("train_date_end") or snapshot_doc.get("date_end")
    training_yms = artifact.get("training_yms") or snapshot_doc.get("selected_yms") or []
    if not training_yms:
        provenance = snapshot_doc.get("source_provenance") or {}
        datasets = provenance.get("datasets") or provenance.get("dataset_manifests") or []
        for dataset in datasets:
            if isinstance(dataset, dict):
                training_yms.extend(_period_months(dataset.get("date_start", ""), dataset.get("date_end", "")))
    if not training_yms:
        training_yms = _period_months(start or "", end or "")
    threshold = artifact.get("threshold") or {}
    calibration_yms = artifact.get("calibration_yms") or threshold.get("calibration_yms") or []
    return {"train_date_start": start, "train_date_end": end,
            "training_yms": sorted(set(training_yms)), "calibration_yms": sorted(set(calibration_yms))}


def validate_release_manifest_schema(release_doc: dict) -> dict:
    """Validate release manifest against schemas/operational_release_manifest.schema.json."""
    schema = read_json(RELEASE_SCHEMA_PATH)
    required_top = set(schema["required"])
    if set(release_doc.keys()) != required_top:
        missing = required_top - set(release_doc.keys())
        extra = set(release_doc.keys()) - required_top
        raise ValueError(f"Release manifest 최상위 키 불일치 (누락={missing}, 추가={extra})")
    if release_doc.get("schema_version") != "1.0":
        raise ValueError("Release manifest schema_version은 '1.0'이어야 합니다.")
    if release_doc.get("sea") not in {"EAST", "WEST", "SOUTH", "ALL"}:
        raise ValueError("Release manifest sea 값이 올바르지 않습니다.")
    for key in ("source", "environment", "mapping"):
        art = release_doc[key]
        if set(art.keys()) != {"uri", "sha256"} or not re.fullmatch(r"[A-Fa-f0-9]{64}", art["sha256"]):
            raise ValueError(f"Release manifest {key} 아티팩트 형식 오류")
    data_art = release_doc["data"]
    if set(data_art.keys()) != {"uri", "sha256", "period_start", "period_end"} or not re.fullmatch(r"[A-Fa-f0-9]{64}", data_art["sha256"]):
        raise ValueError("Release manifest data 아티팩트 형식 오류")
    models = release_doc["models"]
    if not isinstance(models, list) or len(models) < 1:
        raise ValueError("Release manifest models 배열이 비어 있습니다.")
    model_schema = schema["properties"]["models"]["items"]
    required_model_keys = set(model_schema["required"])
    allowed_model_keys = set(model_schema["properties"])
    for item in models:
        if not required_model_keys <= set(item) or not set(item) <= allowed_model_keys:
            raise ValueError("Release manifest model 항목 필드 불일치")
        for role in ("model", "scaler", "threshold", "threshold_metadata"):
            if role not in item:
                continue
            if set(item[role].keys()) != {"uri", "sha256"} or not re.fullmatch(r"[A-Fa-f0-9]{64}", item[role]["sha256"]):
                raise ValueError(f"Release manifest model.{role} 해시 형식 오류")
    approval = release_doc["approval"]
    if set(approval.keys()) != {"status", "approved_by", "approved_at"}:
        raise ValueError("Release manifest approval 필드 불일치")
    if approval["status"] not in {"DRAFT", "CANDIDATE", "APPROVED", "RETIRED"}:
        raise ValueError("Release manifest approval.status 값 오류")
    return {"passed": True, "schema_id": schema["$id"], "model_count": len(models)}


def _mlflow_client(store: Path = STORE):
    MlflowClient = importlib.import_module("mlflow.tracking").MlflowClient
    store = store.resolve()
    store.mkdir(parents=True, exist_ok=True)
    uri = "sqlite:///" + (store / "tracking.db").as_posix()
    return MlflowClient(tracking_uri=uri, registry_uri=uri), uri


def register_candidate_in_mlflow(
    run_id: str,
    store: Path = STORE,
    manifest_path: Path = MANIFEST,
) -> dict:
    run_folder = CANDIDATE_RUNS_ROOT / run_id
    artifact_path = run_folder / "artifact.json"
    comparison_path = run_folder / "comparison.json"
    if not artifact_path.is_file() or not comparison_path.is_file():
        raise ValueError(f"후보 실행 산출물이 없습니다: {run_id}")

    artifact = read_json(artifact_path)
    comparison = duel_comparison(read_json(comparison_path))
    if artifact.get("status") != "FINISHED" or artifact.get("worker_failure") or (run_folder / "worker_failure.json").is_file():
        raise ValueError("완료되지 않은 후보 실행은 MLflow에 등록하지 않습니다.")
    bundle = artifact.get("bundle") or {}
    if not isinstance(bundle, dict) or not {"model", "scaler", "threshold"} <= set(bundle):
        raise ValueError("후보 번들의 필수 역할이 누락되었습니다.")
    verified_assets = []
    for role, fname in (
        ("model", "residual_lstm_forecast.h5"),
        ("scaler", "scaler.forecast.gz"),
        ("threshold", "Thres.forecast.DEV"),
        ("threshold_metadata", "threshold_metadata.json"),
    ):
        if role == "threshold_metadata" and role not in bundle:
            continue
        info = bundle[role]
        if not isinstance(info, dict) or "path" not in info or "sha256" not in info:
            raise ValueError(f"후보 번들 {role} 파일 정보가 올바르지 않습니다.")
        bpath = run_folder / "bundle" / fname
        if role == "threshold_metadata":
            bpath = resolve_project_path(info["path"], BASE)
        if not bpath.is_file() or sha256(bpath) != info["sha256"]:
            if role == "threshold_metadata":
                raise ValueError("임계값 메타데이터 파일 해시가 다릅니다.")
            raise ValueError(f"번들 파일 해시 불일치: {fname}")
        verified_assets.append((bpath, info["sha256"]))
    manifest = read_json(manifest_path)
    validate(manifest)

    station = artifact["station"]
    sensor = artifact["sensor"]
    model_name = f"LOCAL_TRIAL_{station}_{sensor}"

    client, uri = _mlflow_client(store)
    exp_name = "OceanDB_AI_LOCAL_TRIAL"
    experiment = client.get_experiment_by_name(exp_name)
    experiment_id = (
        experiment.experiment_id
        if experiment
        else client.create_experiment(exp_name, artifact_location=(store / "artifacts").as_uri())
    )

    comparison_contract = "champion-candidate-1"
    existing = client.search_runs(
        [experiment_id],
        filter_string=(f"tags.candidate_run_id = '{run_id}' "
                       f"AND tags.comparison_contract = '{comparison_contract}'"),
        max_results=1,
    )
    mlflow_run = (
        existing[0]
        if existing
        else client.create_run(
            experiment_id,
            tags={
                "mlflow.runName": f"candidate_{station}_{sensor}_{run_id}",
                "candidate_run_id": run_id,
                "comparison_contract": comparison_contract,
                "station": station,
                "sensor": sensor,
                "snapshot_id": artifact["snapshot_id"],
                "dataset_id": artifact["dataset_id"],
                "domain": "fixed_station",
                "item_id": "tide",
                "target_variable": "TIDE_LEVEL",
                "evidence_level": "ISOLATED_RUNTIME_CANDIDATE_TRAINING",
                "operational_deployment": "false",
                "ai_flag_position": "11",
            },
        )
    )
    mlflow_run_id = mlflow_run.info.run_id
    if comparison.get("evaluation_mode"):
        client.set_tag(mlflow_run_id, "evaluation_mode", str(comparison["evaluation_mode"]))

    hp = {key: value for key, value in artifact["hyperparameters"].items() if key != "ridge_alphas"}
    for k, v in hp.items():
        client.log_param(mlflow_run_id, k, json.dumps(v) if isinstance(v, list) else str(v))
    client.log_param(mlflow_run_id, "snapshot_id", artifact["snapshot_id"])
    client.log_param(mlflow_run_id, "dataset_id", artifact["dataset_id"])
    if artifact.get("worker_python"):
        client.log_param(mlflow_run_id, "worker_python", artifact["worker_python"])

    models_cmp = comparison["models"]
    metrics_to_log = {
        "test_candidate_mae": models_cmp["candidate"]["mae"],
        "test_candidate_rmse": models_cmp["candidate"]["rmse"],
        "test_champion_2025_mae": models_cmp["champion_2025"]["mae"],
        "test_champion_2025_rmse": models_cmp["champion_2025"]["rmse"],
        "raw_threshold_3sigma_cm": artifact["threshold"]["raw_threshold_3sigma_cm"],
        "effective_sigma": float(artifact["threshold"]["effective_sigma"]),
        "effective_threshold_cm": artifact["threshold"]["effective_threshold_cm"],
        "candidate_latency_ms": models_cmp["candidate"]["latency"]["total_ms"],
        "elapsed_seconds": artifact["elapsed_seconds"],
    }
    for m_name in DUEL_MODEL_KEYS:
        cls_info = models_cmp.get(m_name, {}).get("classification")
        if isinstance(cls_info, dict) and cls_info.get("f1_score_100") is not None:
            metrics_to_log[f"test_{m_name}_f1_score_100"] = float(cls_info["f1_score_100"])
        if isinstance(cls_info, dict) and cls_info.get("normal_f1_score_100") is not None:
            metrics_to_log[f"test_{m_name}_normal_f1_score_100"] = float(cls_info["normal_f1_score_100"])
    cand_cls = models_cmp.get("candidate", {}).get("classification")
    if isinstance(cand_cls, dict):
        for cls_key in ("precision_100", "recall_100", "specificity_100", "accuracy_100", "tp", "fp", "tn", "fn"):
            if cand_cls.get(cls_key) is not None:
                metrics_to_log[f"test_candidate_{cls_key}"] = float(cand_cls[cls_key])
    for m_key, m_val in metrics_to_log.items():
        client.log_metric(mlflow_run_id, m_key, float(m_val))

    # Project archived diagnostics into temporary upload files; source bytes remain evidence.
    with tempfile.TemporaryDirectory(prefix="ai_qc_duel_registration_") as upload_folder:
        for fname in ("comparison.json", "replay_verification.json", "series_comparison.json", "artifact.json"):
            fpath = run_folder / fname
            if fpath.is_file():
                payload = read_json(fpath)
                projected = duel_comparison(payload) if fname == "comparison.json" else duel_series(payload)
                if fname == "artifact.json":
                    projected["source_comparison_sha256"] = sha256(comparison_path)
                    projected["comparison_sha256"] = sha256(Path(upload_folder) / "comparison.json")
                upload_path = Path(upload_folder) / fname
                write_json(upload_path, projected)
                client.log_artifact(mlflow_run_id, str(upload_path), "evidence")

    asset_subpath = f"model_assets/{station}/{sensor}"
    for bpath, expected_sha in verified_assets:
        if not bpath.is_file() or sha256(bpath) != expected_sha:
            raise ValueError(f"번들 파일 해시 불일치: {bpath.name}")
        client.log_artifact(mlflow_run_id, str(bpath), asset_subpath)

    status = "FINISHED" if artifact["status"] == "FINISHED" else "FAILED"
    client.set_terminated(mlflow_run_id, status=status)

    matches = client.search_registered_models(filter_string=f"name = '{model_name}'")
    if not matches:
        client.create_registered_model(
            model_name,
            tags={"scope": "LOCAL_TRIAL_ONLY", "operational_deployment": "false"},
        )

    source_uri = client.get_run(mlflow_run_id).info.artifact_uri + "/" + asset_subpath
    existing_versions = client.search_model_versions(
        filter_string=f"name = '{model_name}' AND run_id = '{mlflow_run_id}'"
    )
    version = (
        existing_versions[0]
        if existing_versions
        else client.create_model_version(
            model_name,
            source=source_uri,
            run_id=mlflow_run_id,
            tags={
                "evidence_level": "CANDIDATE_TRAINED_AND_2MODEL_COMPARED",
                "candidate_run_id": run_id,
                "snapshot_id": artifact["snapshot_id"],
                "source_model_sha256": artifact["bundle"]["model"]["sha256"],
                "raw_threshold_3sigma_cm": str(artifact["threshold"]["raw_threshold_3sigma_cm"]),
                "effective_threshold_cm": str(artifact["threshold"]["effective_threshold_cm"]),
            },
        )
    )
    if version.status != "READY":
        raise ValueError(f"MLflow 모델 버전이 READY 상태가 아닙니다: {model_name} v{version.version}")
    client.set_model_version_tag(model_name, str(version.version), "evidence_level", "CANDIDATE_TRAINED_AND_2MODEL_COMPARED")

    client.set_registered_model_alias(model_name, "candidate", version.version)
    loaded = client.get_model_version_by_alias(model_name, "candidate")
    if str(loaded.version) != str(version.version):
        raise ValueError("MLflow candidate alias 설정 확인 실패")

    reg_info = {
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "tracking_uri": uri,
        "experiment_id": experiment_id,
        "mlflow_run_id": mlflow_run_id,
        "model_name": model_name,
        "model_version": str(version.version),
        "alias": "candidate",
    }
    artifact["mlflow_registration"] = reg_info
    write_json(artifact_path, artifact)
    return reg_info


def _extract_worker_progress(run_folder: Path, epochs: int, started_monotonic: float) -> dict | None:
    diag_path = run_folder / "training_diagnostics.json"
    if not diag_path.is_file():
        return None
    try:
        diag = read_json(diag_path)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(diag, dict):
        return None
    last_stage = str(diag.get("last_stage") or "worker_start")
    ev_candidate = diag.get("events")
    if not isinstance(ev_candidate, list):
        ev_candidate = diag.get("stages")
    events = ev_candidate if isinstance(ev_candidate, list) else []
    last_ev: dict = events[-1] if events and isinstance(events[-1], dict) else {}
    latest_epoch_ev = next(
        (ev for ev in reversed(events) if isinstance(ev, dict) and ev.get("stage") == "epoch_end"),
        None,
    )
    ep_ev: dict = latest_epoch_ev if isinstance(latest_epoch_ev, dict) else {}
    ep_num = int(ep_ev.get("epoch") or last_ev.get("epoch") or 0)
    ep_tot = max(1, int(last_ev.get("epochs_total") or ep_ev.get("epochs_total") or epochs or 1))
    ep_metrics = ep_ev.get("metrics")
    raw_metrics: dict = ep_metrics if isinstance(ep_metrics, dict) else {}
    metrics: dict = {}
    for k in ("loss", "val_loss", "mae", "val_mae"):
        val = raw_metrics.get(k, ep_ev.get(k))
        if val is not None:
            metrics[k] = val

    stage_index = min(4, max(1, int(last_ev.get("stage_index") or 1)))
    percent = float(last_ev.get("percent") or 5.0)
    if last_stage in {"worker_start", "tensorflow_init_start", "tensorflow_init_end", "scaler_fit", "ridge_fit"}:
        stage_index = 1
        percent = max(percent, 10.0 if last_stage == "scaler_fit" else 6.0)
    elif last_stage in {
        "model_build_start", "model_build_end", "inputs_validated",
        "fit_start", "first_batch_start", "first_batch_end", "epoch_end", "fit_end",
    }:
        stage_index = 2
        if last_stage == "fit_end":
            percent = 75.0
        elif ep_num > 0:
            percent = round(25.0 + 50.0 * min(1.0, ep_num / ep_tot), 1)
        else:
            percent = max(percent, 25.0)
    elif last_stage in {
        "threshold_calibration_start", "threshold_calibration_end",
        "save_start", "save_end", "evaluate_start",
    }:
        stage_index = 3
        percent = max(percent, 86.0 if last_stage == "evaluate_start" else 80.0)
    elif last_stage in {"replay_start", "evaluate_end", "finished"}:
        stage_index = 4
        percent = max(percent, 95.0 if last_stage in {"evaluate_end", "finished"} else 92.0)

    return {
        "stage": last_stage,
        "stage_index": stage_index,
        "stage_total": 4,
        "percent": round(min(99.0, max(1.0, percent)), 1),
        "epoch": ep_num,
        "epochs_total": ep_tot,
        "loss": metrics.get("loss"),
        "val_loss": metrics.get("val_loss"),
        "mae": metrics.get("mae"),
        "val_mae": metrics.get("val_mae"),
        "metrics": metrics,
        "elapsed_seconds": round(max(0.0, time.monotonic() - started_monotonic), 1),
    }


def run_candidate_training_subprocess(
    snapshot_id: str,
    epochs: int = DEFAULT_EPOCHS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    seed: int = 42,
    eval_snapshot_id: str | None = None,
    eval_scope: str = "AUTO",
    store: Path = STORE,
    manifest_path: Path = MANIFEST,
    tf_python: Path = TF_PYTHON,
    progress=None,
) -> dict:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    worker_script = BASE / "scripts/candidate_training_worker.py"
    command = [
        str(tf_python.resolve(strict=True)),
        "-X",
        "utf8",
        "-X",
        "faulthandler",
        str(worker_script),
        "--mode",
        "train",
        "--snapshot-id",
        snapshot_id,
        "--run-id",
        run_id,
        "--epochs",
        str(int(epochs)),
        "--batch-size",
        str(int(batch_size)),
        "--seed",
        str(int(seed)),
        "--manifest",
        str(manifest_path.resolve(strict=True)),
    ]
    run_folder = CANDIDATE_RUNS_ROOT / run_id
    run_folder.mkdir(parents=True, exist_ok=True)
    started_monotonic = time.monotonic()
    last_emitted: dict = {}

    def _emit(payload: dict) -> None:
        nonlocal last_emitted
        if not callable(progress):
            return
        merged = {
            **last_emitted,
            **payload,
            "run_id": run_id,
            "elapsed_seconds": round(max(0.0, time.monotonic() - started_monotonic), 1),
        }
        last_emitted = merged
        progress(merged)

    _emit({
        "stage": "worker_start",
        "stage_index": 1,
        "stage_total": 4,
        "percent": 5.0,
        "epoch": 0,
        "epochs_total": int(epochs),
        "message": "TensorFlow 워커 초기화 및 스냅샷 로드 중",
    })

    stop_poll = threading.Event()
    poll_thread: threading.Thread | None = None
    if callable(progress):
        def _poll_diagnostics() -> None:
            prev_sig = None
            while not stop_poll.wait(0.15):
                prog = _extract_worker_progress(run_folder, int(epochs), started_monotonic)
                if prog is not None:
                    sig = (prog.get("stage"), prog.get("epoch"), prog.get("percent"), int(prog.get("elapsed_seconds", 0)))
                    if sig != prev_sig:
                        prev_sig = sig
                        _emit(prog)

        poll_thread = threading.Thread(target=_poll_diagnostics, daemon=True)
        poll_thread.start()

    try:
        try:
            with (run_folder / "stdout.log").open("wb") as out, (run_folder / "stderr.log").open("wb") as err:
                completed = subprocess.run(
                    command, cwd=BASE, stdout=out, stderr=err, timeout=1800, check=False, shell=False,
                )
        except subprocess.TimeoutExpired as exc:
            error = WorkerExecutionError("후보 모델 학습 제한 시간을 넘었습니다.", run_id, run_folder, None, timed_out=True)
            _record_worker_failure(error, run_folder)
            raise error from exc
        except OSError as exc:
            error = WorkerExecutionError(f"후보 모델 학습 워커를 실행하지 못했습니다: {exc}", run_id, run_folder, None)
            _record_worker_failure(error, run_folder)
            raise error from exc
    finally:
        stop_poll.set()
        if poll_thread is not None:
            poll_thread.join(timeout=1.0)
        final_diag_prog = _extract_worker_progress(run_folder, int(epochs), started_monotonic)
        if final_diag_prog is not None:
            _emit(final_diag_prog)

    if completed.returncode != 0:
        err_tail = (run_folder / "stderr.log").read_text(encoding="utf-8", errors="replace")[-3000:]
        error = WorkerExecutionError(f"후보 모델 학습 워커 실패 (코드 {completed.returncode}): {err_tail}",
                                     run_id, run_folder, completed.returncode)
        _record_worker_failure(error, run_folder)
        raise error

    artifact_path = run_folder / "artifact.json"
    completed_artifact = read_json(artifact_path)
    completed_artifact["worker_python"] = str(tf_python.resolve(strict=True))
    write_json(artifact_path, completed_artifact)
    hist = completed_artifact.get("training_history") or {}
    loss_list = hist.get("loss") or []
    val_loss_list = hist.get("val_loss") or []
    mae_list = hist.get("mae") or []
    val_mae_list = hist.get("val_mae") or []
    epochs_trained = int((completed_artifact.get("hyperparameters") or {}).get("epochs_trained") or len(loss_list) or epochs)
    _emit({
        "stage": "mlflow_register",
        "stage_index": 4,
        "stage_total": 4,
        "percent": 96.0,
        "epoch": epochs_trained,
        "epochs_total": int(epochs),
        "loss": loss_list[-1] if loss_list else last_emitted.get("loss"),
        "val_loss": val_loss_list[-1] if val_loss_list else last_emitted.get("val_loss"),
        "mae": mae_list[-1] if mae_list else last_emitted.get("mae"),
        "val_mae": val_mae_list[-1] if val_mae_list else last_emitted.get("val_mae"),
        "message": "Replay 검증 통과 · MLflow 후보 모델 등록 중",
    })
    mlflow_info = register_candidate_in_mlflow(run_id, store=store, manifest_path=manifest_path)
    if eval_snapshot_id and str(eval_snapshot_id).strip():
        target_eval = str(eval_snapshot_id).strip()
        scope_norm = str(eval_scope or "AUTO").strip().upper()
        if target_eval != snapshot_id or scope_norm == "ALL":
            _emit({
                "stage": "cross_evaluate",
                "stage_index": 4,
                "stage_total": 4,
                "percent": 98.0,
                "epoch": epochs_trained,
                "epochs_total": int(epochs),
                "message": f"외부 평가 스냅샷({target_eval}) Champion 2025와 신규 후보 비교 중",
            })
            run_candidate_evaluation_subprocess(
                run_id=run_id,
                eval_snapshot_id=target_eval,
                eval_scope=scope_norm,
                manifest_path=manifest_path,
                tf_python=tf_python,
            )
    _emit({
        "stage": "finished",
        "stage_index": 4,
        "stage_total": 4,
        "percent": 100.0,
        "epoch": epochs_trained,
        "epochs_total": int(epochs),
        "message": "후보 모델 학습 및 MLflow 등록 완료",
    })
    return {
        "run_id": run_id,
        "mlflow_registration": mlflow_info,
        "artifact": duel_series(read_json(run_folder / "artifact.json")),
        "comparison": duel_comparison(read_json(run_folder / "comparison.json")),
    }


def run_candidate_evaluation_subprocess(
    run_id: str,
    eval_snapshot_id: str,
    eval_scope: str = "AUTO",
    manifest_path: Path = MANIFEST,
    tf_python: Path = TF_PYTHON,
) -> dict:
    run_folder = CANDIDATE_RUNS_ROOT / run_id
    artifact_path = run_folder / "artifact.json"
    if not artifact_path.is_file():
        raise ValueError(f"후보 실행 기록을 찾을 수 없습니다: {run_id}")
    if not eval_snapshot_id or not str(eval_snapshot_id).strip():
        raise ValueError("평가할 대상 스냅샷 ID(eval_snapshot_id)를 선택해 주세요.")
    artifact = read_json(artifact_path)
    worker_script = BASE / "scripts/candidate_training_worker.py"
    scope_clean = str(eval_scope or "AUTO").strip().upper()
    command = [
        str(tf_python.resolve(strict=True)),
        "-X",
        "utf8",
        "-X",
        "faulthandler",
        str(worker_script),
        "--mode",
        "evaluate",
        "--snapshot-id",
        artifact["snapshot_id"],
        "--eval-snapshot-id",
        str(eval_snapshot_id).strip(),
        "--eval-scope",
        scope_clean,
        "--run-id",
        run_id,
        "--manifest",
        str(manifest_path.resolve(strict=True)),
    ]
    with (run_folder / "evaluate.stdout.log").open("wb") as out, (run_folder / "evaluate.stderr.log").open("wb") as err:
        completed = subprocess.run(
            command,
            cwd=BASE,
            stdout=out,
            stderr=err,
            timeout=900,
            check=False,
            shell=False,
        )
    if completed.returncode != 0:
        err_tail = (run_folder / "evaluate.stderr.log").read_text(encoding="utf-8", errors="replace")[-2000:]
        raise RuntimeError(f"타 기간 스냅샷 교차 평가 실패 (코드 {completed.returncode}): {err_tail}")
    updated_artifact = read_json(artifact_path)
    updated_comparison = read_json(run_folder / "comparison.json")
    return {
        "run_id": run_id,
        "evaluated_snapshot_id": updated_comparison.get("evaluated_snapshot_id", eval_snapshot_id),
        "evaluated_scope": updated_comparison.get("evaluated_scope", scope_clean),
        "evaluated_period": updated_comparison.get("evaluated_period"),
        "artifact": duel_series(updated_artifact),
        "comparison": duel_comparison(updated_comparison),
    }


def run_candidate_replay_subprocess(
    run_id: str,
    manifest_path: Path = MANIFEST,
    tf_python: Path = TF_PYTHON,
) -> dict:
    run_folder = CANDIDATE_RUNS_ROOT / run_id
    artifact_path = run_folder / "artifact.json"
    if not artifact_path.is_file():
        raise ValueError(f"후보 실행 기록을 찾을 수 없습니다: {run_id}")
    artifact = read_json(artifact_path)
    worker_script = BASE / "scripts/candidate_training_worker.py"
    command = [
        str(tf_python.resolve(strict=True)),
        "-X",
        "utf8",
        "-X",
        "faulthandler",
        str(worker_script),
        "--mode",
        "replay",
        "--snapshot-id",
        artifact["snapshot_id"],
        "--run-id",
        run_id,
        "--manifest",
        str(manifest_path.resolve(strict=True)),
    ]
    with (run_folder / "replay.stdout.log").open("wb") as out, (run_folder / "replay.stderr.log").open("wb") as err:
        completed = subprocess.run(
            command,
            cwd=BASE,
            stdout=out,
            stderr=err,
            timeout=600,
            check=False,
            shell=False,
        )
    if completed.returncode != 0:
        err_tail = (run_folder / "replay.stderr.log").read_text(encoding="utf-8", errors="replace")[-2000:]
        raise RuntimeError(f"결정론적 재현 검증 실패 (코드 {completed.returncode}): {err_tail}")
    rv = read_json(run_folder / "replay_verification.json")
    return {**rv, "replay_verification": rv}


def get_model_aliases(station: str, sensor: str, store: Path = STORE) -> dict:
    model_name = f"LOCAL_TRIAL_{station}_{sensor}"
    db_path = store / "tracking.db"
    if not db_path.exists():
        return {"model_name": model_name, "aliases": {}}
    if importlib.util.find_spec("mlflow") is not None:
        client, _ = _mlflow_client(store)
        aliases = {}
        for alias in ("trial", "candidate", "champion", "rollback"):
            try:
                mv = client.get_model_version_by_alias(model_name, alias)
                aliases[alias] = {
                    "version": str(mv.version),
                    "run_id": mv.run_id,
                    "status": mv.status,
                    "candidate_run_id": (mv.tags or {}).get("candidate_run_id"),
                }
            except Exception:
                continue
        return {"model_name": model_name, "aliases": aliases}

    aliases = {}
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        alias_rows = conn.execute(
            "SELECT alias, version FROM registered_model_aliases WHERE name = ?",
            (model_name,),
        ).fetchall()
        ver_rows = {
            str(v): (run_id, status)
            for v, run_id, status in conn.execute(
                "SELECT version, run_id, status FROM model_versions WHERE name = ?",
                (model_name,),
            ).fetchall()
        }
        tag_rows = {
            str(v): val
            for v, val in conn.execute(
                "SELECT version, value FROM model_version_tags WHERE name = ? AND key = 'candidate_run_id'",
                (model_name,),
            ).fetchall()
        }
        for alias, ver in alias_rows:
            if alias in ("trial", "candidate", "champion", "rollback"):
                ver_str = str(ver)
                run_id, status = ver_rows.get(ver_str, (None, "READY"))
                aliases[alias] = {
                    "version": ver_str,
                    "run_id": run_id,
                    "status": status,
                    "candidate_run_id": tag_rows.get(ver_str),
                }
    return {"model_name": model_name, "aliases": aliases}


def _set_model_alias(store: Path, model_name: str, alias: str, version: str) -> None:
    if importlib.util.find_spec("mlflow") is not None:
        client, _ = _mlflow_client(store)
        client.set_registered_model_alias(model_name, alias, str(version))
        return
    db_path = store / "tracking.db"
    if not db_path.exists():
        return
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO registered_model_aliases (name, alias, version) VALUES (?, ?, ?)",
            (model_name, alias, int(version)),
        )
        conn.commit()


def _delete_model_alias(store: Path, model_name: str, alias: str) -> None:
    if importlib.util.find_spec("mlflow") is not None:
        client, _ = _mlflow_client(store)
        try:
            client.delete_registered_model_alias(model_name, alias)
        except Exception:
            pass
        return
    db_path = store / "tracking.db"
    if not db_path.exists():
        return
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            "DELETE FROM registered_model_aliases WHERE name = ? AND alias = ?",
            (model_name, alias),
        )
        conn.commit()


def _normalize_override_paths(override: dict | None) -> dict | None:
    if not isinstance(override, dict):
        return override
    bundle = override.get("bundle")
    if isinstance(bundle, dict):
        for role, role_info in bundle.items():
            if role == "ridge_baseline":
                continue
            if isinstance(role_info, dict) and "path" in role_info:
                role_info["path"] = str(resolve_project_path(role_info["path"], BASE))
    if isinstance(override.get("previous_override"), dict):
        _normalize_override_paths(override["previous_override"])
    return override


def active_release_state() -> dict:
    if not ACTIVE_POINTER_PATH.is_file():
        return {
            "active_release_id": "2025_OPERATION_64_BASELINE",
            "previous_release_id": None,
            "updated_at": None,
            "station_overrides": {},
            "history": [],
        }
    state = read_json(ACTIVE_POINTER_PATH)
    if state.get("active_release_path"):
        state["active_release_path"] = str(resolve_project_path(state["active_release_path"], BASE))
    overrides = state.get("station_overrides")
    if isinstance(overrides, dict):
        for ov in overrides.values():
            _normalize_override_paths(ov)
    return state


def _build_operational_release_manifest(
    release_id: str,
    previous_release_id: str | None,
    sea_code: str,
    snapshot_manifest: dict,
    manifest: dict,
    station_overrides: dict,
    approved_by: str,
    approved_at: str,
) -> dict:
    root = resolve_manifest_root(manifest, BASE)
    indexed_files = {f["path"]: f for f in manifest["files"]}

    # Hash of the 3 sea-level no_update scripts combined as source bundle descriptor
    sea_script_map = {
        "EAST": "AI_QC_east_sea_no_update.py",
        "WEST": "AI_QC_west_sea_no_update.py",
        "SOUTH": "AI_QC_south_sea_no_update.py",
        "ALL": "AI_QC_west_sea_no_update.py",
    }
    source_rel = sea_script_map.get(sea_code, "AI_QC_west_sea_no_update.py")
    source_entry = indexed_files[source_rel]
    mapping_entry = indexed_files["mappingBySea.csv"]

    env_python = TF_PYTHON
    env_sha = sha256(env_python) if env_python.is_file() else hashlib.sha256(b"python3_10_env_restored").hexdigest()

    models_list = []
    for pair in manifest["models"]:
        st = pair["station"]
        sn = pair["sensor"]
        key = f"{st}|{sn}"
        if key in station_overrides:
            ov = station_overrides[key]
            models_list.append({
                "station_code": st,
                "sensor_code": sn,
                "run_id": ov["run_id"],
                "model": {
                    "uri": str(resolve_project_path(ov["bundle"]["model"]["path"], BASE)),
                    "sha256": ov["bundle"]["model"]["sha256"],
                },
                "scaler": {
                    "uri": str(resolve_project_path(ov["bundle"]["scaler"]["path"], BASE)),
                    "sha256": ov["bundle"]["scaler"]["sha256"],
                },
                "threshold": {
                    "uri": str(resolve_project_path(ov["bundle"]["threshold"]["path"], BASE)),
                    "sha256": ov["bundle"]["threshold"]["sha256"],
                },
            })
        else:
            models_list.append({
                "station_code": st,
                "sensor_code": sn,
                "run_id": "2025_OPERATION_64_BASELINE",
                "model": {
                    "uri": str(confined_path(root, pair["model"])),
                    "sha256": indexed_files[pair["model"]]["sha256"],
                },
                "scaler": {
                    "uri": str(confined_path(root, pair["scaler"])),
                    "sha256": indexed_files[pair["scaler"]]["sha256"],
                },
                "threshold": {
                    "uri": str(confined_path(root, pair["threshold"])),
                    "sha256": indexed_files[pair["threshold"]]["sha256"],
                },
            })

    for model_entry in models_list:
        override = station_overrides.get(f"{model_entry['station_code']}|{model_entry['sensor_code']}", {})
        metadata = (override.get("bundle") or {}).get("threshold_metadata")
        if metadata is not None:
            model_entry["threshold_metadata"] = {
                "uri": str(resolve_project_path(metadata["path"], BASE)), "sha256": metadata["sha256"],
            }

    release_doc = {
        "schema_version": "1.0",
        "release_id": release_id,
        "created_at": approved_at,
        "sea": sea_code,
        "previous_release_id": previous_release_id,
        "data": {
            "uri": str(resolve_project_path(snapshot_manifest["parquet"]["path"], BASE)),
            "sha256": snapshot_manifest["parquet"]["sha256"],
            "period_start": f"{snapshot_manifest['date_start']}T00:00:00Z",
            "period_end": f"{snapshot_manifest['date_end']}T23:59:00Z",
        },
        "source": {
            "uri": str(confined_path(root, source_rel)),
            "sha256": source_entry["sha256"],
        },
        "environment": {
            "uri": str(env_python),
            "sha256": env_sha,
        },
        "mapping": {
            "uri": str(confined_path(root, "mappingBySea.csv")),
            "sha256": mapping_entry["sha256"],
        },
        "models": models_list,
        "approval": {
            "status": "APPROVED",
            "approved_by": approved_by,
            "approved_at": approved_at,
        },
    }
    validate_release_manifest_schema(release_doc)
    return release_doc


def _maybe_sync_to_ocean_ai_db(
    snapshot_ids: list[str] | None = None,
    candidate_run_ids: list[str] | None = None,
) -> dict | None:
    db_url = os.environ.get("OCEAN_AI_DATABASE_URL", "").strip()
    if not db_url:
        return None
    with contextlib.suppress(Exception):
        from scripts.ocean_ai_bridge import sync_to_ocean_ai_db

        return sync_to_ocean_ai_db(
            database_url=db_url,
            snapshot_ids=snapshot_ids,
            candidate_run_ids=candidate_run_ids,
        )
    return None


def promote_candidate_to_champion(
    run_id: str,
    approved_by: str,
    reason: str,
    store: Path = STORE,
    manifest_path: Path = MANIFEST,
) -> dict:
    approver = (approved_by or "").strip()
    approval_reason = (reason or "").strip()
    if len(approver) < 2:
        raise ValueError("승인자(approved_by) 이름을 2자 이상 입력해 주세요.")
    if len(approval_reason) < 4:
        raise ValueError("승격 사유(reason)를 4자 이상 입력해 주세요.")

    manifest = read_json(manifest_path)
    before_integrity = validate(manifest)

    run_folder = CANDIDATE_RUNS_ROOT / run_id
    artifact_path = run_folder / "artifact.json"
    comparison_path = run_folder / "comparison.json"
    replay_path = run_folder / "replay_verification.json"
    if not artifact_path.is_file() or not comparison_path.is_file() or not replay_path.is_file():
        raise ValueError(f"승격 대상 실행({run_id})의 필수 검증 파일이 누락되었습니다.")

    artifact = read_json(artifact_path)
    comparison = read_json(comparison_path)
    replay = read_json(replay_path)
    if artifact.get("worker_failure") or (run_folder / "worker_failure.json").is_file():
        raise ValueError("워커 실패 기록이 있는 후보 실행은 승격할 수 없습니다.")
    if artifact.get("status") != "FINISHED" or not replay.get("passed") or not artifact.get("threshold_sanity_passed"):
        raise ValueError("재현 검증 및 임계값 기준을 통과한 후보 모델만 승격할 수 있습니다.")

    # Recompute from the frozen raw counts before registration, aliases or releases change.
    if artifact.get("comparison_sha256") != sha256(comparison_path):
        raise ValueError("후보 기록과 평가 비교 파일의 SHA-256이 다릅니다. 다시 평가해 주세요.")
    if any(comparison.get(key) != artifact.get(key) for key in ("station", "sensor")):
        raise ValueError("후보 기록과 평가 비교 파일의 관측소 또는 센서가 다릅니다.")
    training_snapshot_id = comparison.get("training_snapshot_id") or comparison.get("snapshot_id")
    if not artifact.get("snapshot_id") or training_snapshot_id != artifact["snapshot_id"]:
        raise ValueError("후보 기록과 평가 비교 파일의 학습 스냅샷이 다릅니다.")
    qc_sims = list_local_qc_simulations(candidate_run_id=run_id)
    _, promotion_verdict = _candidate_qc_promotion_verdict(artifact, comparison, qc_sims)
    if not promotion_verdict["promotion_allowed"]:
        raise ValueError(promotion_verdict["recommendation_reason"])

    # Normalize all bundle paths and verify bundle hashes
    if not {"model", "scaler", "threshold"} <= set(artifact.get("bundle") or {}):
        raise ValueError("후보 번들의 필수 역할이 누락되었습니다.")
    for role, binfo in artifact.get("bundle", {}).items():
        if role == "ridge_baseline":
            continue
        if not isinstance(binfo, dict) or "path" not in binfo or "sha256" not in binfo:
            raise ValueError(f"후보 번들 {role} 파일 정보가 올바르지 않습니다.")
        bpath = resolve_project_path(binfo["path"], BASE)
        if not bpath.is_file() and binfo.get("relative_path"):
            bpath = (run_folder / binfo["relative_path"]).resolve()
        binfo["path"] = str(bpath)
        if not bpath.is_file() or sha256(bpath) != binfo["sha256"]:
            raise ValueError(f"후보 번들 {role} 파일 무결성 검증 실패")
    if "threshold_metadata" in artifact["bundle"]:
        worker = importlib.import_module("scripts.candidate_training_worker")
        frozen = worker.load_candidate_threshold(run_folder / "bundle")
        for key in ("raw_threshold_3sigma_cm", "effective_threshold_cm", "threshold_optimization_mode",
                    "operational_deploy_threshold_3sigma_cm", "champion_raw_threshold_3sigma_cm"):
            if frozen.get(key) != (artifact.get("threshold") or {}).get(key):
                raise ValueError(f"후보 기록과 동결된 임계값 메타데이터가 다릅니다: {key}")

    # Snapshot validity is also a read-only precondition, before alias mutations.
    authority = ParquetSnapshotAuthority()
    snapshot_manifest, _ = authority.load_snapshot(artifact["snapshot_id"])

    if "mlflow_registration" not in artifact:
        register_candidate_in_mlflow(run_id, store=store, manifest_path=manifest_path)
        artifact = read_json(artifact_path)

    station = artifact["station"]
    sensor = artifact["sensor"]
    model_name = f"LOCAL_TRIAL_{station}_{sensor}"
    candidate_version = str(artifact["mlflow_registration"]["model_version"])

    aliases_before = get_model_aliases(station, sensor, store=store)["aliases"]

    current_state = active_release_state()
    key = f"{station}|{sensor}"
    station_overrides = dict(current_state.get("station_overrides", {}))
    previous_override = station_overrides.get(key)

    # Determine previous champion version (or trial baseline version) to assign as rollback
    prev_champion_version = None
    if previous_override and previous_override.get("run_id") == run_id:
        prev_champion_version = previous_override.get("rollback_version")
        previous_override = previous_override.get("previous_override")
    elif "champion" in aliases_before and str(aliases_before["champion"]["version"]) != candidate_version:
        prev_champion_version = aliases_before["champion"]["version"]
    elif "rollback" in aliases_before and str(aliases_before["rollback"]["version"]) != candidate_version:
        prev_champion_version = aliases_before["rollback"]["version"]
    elif "trial" in aliases_before:
        prev_champion_version = aliases_before["trial"]["version"]

    if prev_champion_version is not None and str(prev_champion_version) != candidate_version:
        _set_model_alias(store, model_name, "rollback", str(prev_champion_version))

    _set_model_alias(store, model_name, "champion", candidate_version)
    aliases_after = get_model_aliases(station, sensor, store=store)["aliases"]

    previous_release_id = current_state["active_release_id"]
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    release_id = f"REL_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{station}_{sensor}_{uuid.uuid4().hex[:6]}"
    sea_code = SEA_CODE_MAP.get(artifact.get("sea", ""), "ALL")

    station_overrides[key] = {
        "station": station,
        "sensor": sensor,
        "run_id": run_id,
        "snapshot_id": artifact["snapshot_id"],
        "mlflow_model_name": model_name,
        "champion_version": candidate_version,
        "rollback_version": prev_champion_version,
        "previous_override": previous_override,
        "bundle": {role: info for role, info in artifact["bundle"].items() if role != "ridge_baseline"},
        "threshold": artifact["threshold"],
        "promoted_at": now_iso,
        "approved_by": approver,
        "reason": approval_reason,
    }

    release_doc = _build_operational_release_manifest(
        release_id=release_id,
        previous_release_id=previous_release_id,
        sea_code=sea_code,
        snapshot_manifest=snapshot_manifest,
        manifest=manifest,
        station_overrides=station_overrides,
        approved_by=approver,
        approved_at=now_iso,
    )
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    release_path = RELEASES_DIR / f"{release_id}.json"
    write_json(release_path, release_doc)
    release_sha = sha256(release_path)

    deployment_id = f"DEP_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    deployment_record = {
        "schema_version": "ocean-ai-deployment-1",
        "deployment_id": deployment_id,
        "action": "PROMOTE_CANDIDATE_TO_CHAMPION",
        "created_at": now_iso,
        "domain": "fixed_station",
        "item_id": "tide",
        "target_variable": "TIDE_LEVEL",
        "station": station,
        "sensor": sensor,
        "sea": artifact["sea"],
        "candidate_run_id": run_id,
        "snapshot_id": artifact["snapshot_id"],
        "champion_version": str(candidate_version),
        "rollback_version": str(prev_champion_version) if prev_champion_version is not None else None,
        "release_id": release_id,
        "previous_release_id": previous_release_id,
        "release_manifest_path": str(release_path),
        "release_manifest_sha256": release_sha,
        "approved_by": approver,
        "reason": approval_reason,
        "mlflow_model_name": model_name,
        "aliases_before": aliases_before,
        "aliases_after": aliases_after,
        "comparison_summary": {
            "promotion_verdict": promotion_verdict,
            "candidate_mae": comparison["models"]["candidate"]["mae"],
            "champion_2025_mae": comparison["models"]["champion_2025"]["mae"],
            "candidate_f1_score_100": (comparison["models"]["candidate"].get("classification") or {}).get("f1_score_100"),
            "champion_2025_f1_score_100": (comparison["models"]["champion_2025"].get("classification") or {}).get("f1_score_100"),
            "candidate_threshold": artifact["threshold"],
        },
        "legacy_ai_modified": False,
        "operational_database_used": False,
        "inputs_before": before_integrity,
        "inputs_after": validate(manifest),
    }
    DEPLOYMENTS_DIR.mkdir(parents=True, exist_ok=True)
    write_json(DEPLOYMENTS_DIR / f"{deployment_id}.json", deployment_record)

    history = list(current_state.get("history", []))
    history.insert(0, {
        "deployment_id": deployment_id,
        "action": "PROMOTE",
        "release_id": release_id,
        "previous_release_id": previous_release_id,
        "station": station,
        "sensor": sensor,
        "run_id": run_id,
        "champion_version": candidate_version,
        "rollback_version": prev_champion_version,
        "approved_by": approver,
        "reason": approval_reason,
        "timestamp": now_iso,
    })
    new_pointer = {
        "active_release_id": release_id,
        "active_release_path": str(release_path),
        "active_release_sha256": release_sha,
        "previous_release_id": previous_release_id,
        "updated_at": now_iso,
        "station_overrides": station_overrides,
        "history": history[:50],
    }
    write_json(ACTIVE_POINTER_PATH, new_pointer)

    artifact["promotion"] = {
        "status": "PROMOTED_TO_CHAMPION",
        "deployment_id": deployment_id,
        "release_id": release_id,
        "approved_by": approver,
        "approved_at": now_iso,
        "reason": approval_reason,
    }
    write_json(artifact_path, artifact)
    sync_res = _maybe_sync_to_ocean_ai_db(
        snapshot_ids=[artifact["snapshot_id"]],
        candidate_run_ids=[run_id],
    )
    if sync_res is not None:
        deployment_record["ocean_ai_sync"] = sync_res
    return deployment_record


def rollback_champion(
    station: str,
    sensor: str,
    approved_by: str,
    reason: str,
    store: Path = STORE,
    manifest_path: Path = MANIFEST,
) -> dict:
    approver = (approved_by or "").strip()
    rollback_reason = (reason or "").strip()
    if len(approver) < 2:
        raise ValueError("승인자(approved_by) 이름을 2자 이상 입력해 주세요.")
    if len(rollback_reason) < 4:
        raise ValueError("롤백 사유(reason)를 4자 이상 입력해 주세요.")

    manifest = read_json(manifest_path)
    before_integrity = validate(manifest)

    key = f"{station}|{sensor}"
    current_state = active_release_state()
    station_overrides = dict(current_state.get("station_overrides", {}))
    if key not in station_overrides:
        raise ValueError(f"{station} / {sensor} 조합은 현재 승격된 오버라이드가 없어 롤백할 대상이 없습니다.")

    current_override = station_overrides[key]
    model_name = f"LOCAL_TRIAL_{station}_{sensor}"
    aliases_before = get_model_aliases(station, sensor, store=store)["aliases"]
    if "rollback" not in aliases_before:
        raise ValueError(f"MLflow 레지스트리에 {model_name}의 rollback alias가 없습니다.")

    rollback_version = aliases_before["rollback"]["version"]
    demoted_version = aliases_before.get("champion", {}).get("version")
    prev_ov = current_override.get("previous_override")

    # Restore champion alias to rollback version, and keep demoted version as candidate
    _set_model_alias(store, model_name, "champion", str(rollback_version))
    if demoted_version is not None:
        _set_model_alias(store, model_name, "candidate", str(demoted_version))
    next_rollback = prev_ov.get("rollback_version") if prev_ov else None
    if next_rollback is not None and str(next_rollback) != str(rollback_version):
        _set_model_alias(store, model_name, "rollback", str(next_rollback))
    else:
        _delete_model_alias(store, model_name, "rollback")
    aliases_after = get_model_aliases(station, sensor, store=store)["aliases"]

    previous_release_id = current_state["active_release_id"]
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    release_id = f"REL_ROLLBACK_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{station}_{sensor}_{uuid.uuid4().hex[:6]}"

    authority = ParquetSnapshotAuthority()
    snapshot_manifest, _ = authority.load_snapshot(current_override["snapshot_id"])

    if prev_ov:
        station_overrides[key] = _normalize_override_paths(prev_ov)
    else:
        del station_overrides[key]

    release_doc = _build_operational_release_manifest(
        release_id=release_id,
        previous_release_id=previous_release_id,
        sea_code="ALL",
        snapshot_manifest=snapshot_manifest,
        manifest=manifest,
        station_overrides=station_overrides,
        approved_by=approver,
        approved_at=now_iso,
    )
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    release_path = RELEASES_DIR / f"{release_id}.json"
    write_json(release_path, release_doc)
    release_sha = sha256(release_path)

    deployment_id = f"DEP_ROLLBACK_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    deployment_record = {
        "schema_version": "ocean-ai-deployment-1",
        "deployment_id": deployment_id,
        "action": "ROLLBACK_CHAMPION",
        "created_at": now_iso,
        "domain": "fixed_station",
        "item_id": "tide",
        "target_variable": "TIDE_LEVEL",
        "station": station,
        "sensor": sensor,
        "champion_version": str(rollback_version),
        "restored_champion_version": str(rollback_version),
        "demoted_version": str(demoted_version) if demoted_version else None,
        "release_id": release_id,
        "previous_release_id": previous_release_id,
        "release_manifest_path": str(release_path),
        "release_manifest_sha256": release_sha,
        "approved_by": approver,
        "reason": rollback_reason,
        "mlflow_model_name": model_name,
        "aliases_before": aliases_before,
        "aliases_after": aliases_after,
        "legacy_ai_modified": False,
        "operational_database_used": False,
        "inputs_before": before_integrity,
        "inputs_after": validate(manifest),
    }
    DEPLOYMENTS_DIR.mkdir(parents=True, exist_ok=True)
    write_json(DEPLOYMENTS_DIR / f"{deployment_id}.json", deployment_record)

    history = list(current_state.get("history", []))
    history.insert(0, {
        "deployment_id": deployment_id,
        "action": "ROLLBACK",
        "release_id": release_id,
        "previous_release_id": previous_release_id,
        "station": station,
        "sensor": sensor,
        "run_id": prev_ov["run_id"] if prev_ov else "2025_OPERATION_64_BASELINE",
        "champion_version": str(rollback_version),
        "demoted_version": str(demoted_version) if demoted_version else None,
        "approved_by": approver,
        "reason": rollback_reason,
        "timestamp": now_iso,
    })
    new_pointer = {
        "active_release_id": release_id,
        "active_release_path": str(release_path),
        "active_release_sha256": release_sha,
        "previous_release_id": previous_release_id,
        "updated_at": now_iso,
        "station_overrides": station_overrides,
        "history": history[:50],
    }
    write_json(ACTIVE_POINTER_PATH, new_pointer)
    sync_res = _maybe_sync_to_ocean_ai_db(
        snapshot_ids=[current_override["snapshot_id"]],
        candidate_run_ids=[current_override["run_id"]],
    )
    if sync_res is not None:
        deployment_record["ocean_ai_sync"] = sync_res
    return deployment_record


def _default_local_qc_root(sim_root: Path | None = None) -> Path:
    if sim_root is not None:
        return Path(sim_root)
    if CANDIDATE_RUNS_ROOT != BASE / "reports/candidate_runs" and LOCAL_QC_SIMULATIONS_ROOT == BASE / "reports/local_qc_simulations":
        return CANDIDATE_RUNS_ROOT.parent / "local_qc_simulations"
    return LOCAL_QC_SIMULATIONS_ROOT


def _canonical_local_qc_span(snapshot_id: str, scope: str) -> tuple[datetime, datetime]:
    """Use the CLI's authoritative full snapshot interval, never a requested subrange."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", snapshot_id or ""):
        raise ValueError("전체 평가 범위를 확인할 스냅샷 ID가 없습니다.")
    simulator = importlib.import_module("scripts.local_qc_simulator")
    start, end = simulator._period(snapshot_id, None, scope, None, None, BASE)
    return datetime.fromisoformat(str(start)), datetime.fromisoformat(str(end))

def _local_qc_evidence_status(comp: dict, comp_sha: str, folder: Path) -> dict:
    """Match frozen replay inputs to today's actual bundle, including the consumed DEV float."""
    verdict = local_qc_promotion_verdict(comp)
    policy_current = bool(verdict.get("policy_current"))
    reasons = []
    try:
        run_id = str(comp.get("candidate_run_id") or "")
        if not re.fullmatch(r"\d{8}T\d{6}Z_[0-9a-f]{8}", run_id):
            raise ValueError("시뮬레이션의 후보 실행 ID가 올바르지 않습니다.")
        artifact_path = CANDIDATE_RUNS_ROOT / run_id / "artifact.json"
        artifact = read_json(artifact_path)
        if any(artifact.get(key) != comp.get(key) for key in ("station", "sensor")):
            raise ValueError("시뮬레이션과 현재 후보의 관측소·센서가 다릅니다.")
        actual = artifact.get("bundle") or {}
        recorded = ((comp.get("bundle_metadata") or {}).get("candidate") or {}).get("artifacts") or {}
        for role in ("model", "scaler", "threshold", "threshold_metadata"):
            info, previous = actual.get(role), recorded.get(role)
            if not isinstance(info, dict) or not isinstance(previous, dict):
                raise ValueError(f"현재 후보와 시뮬레이션의 {role} 해시 근거가 없습니다.")
            path = resolve_project_path(info.get("path") or "", BASE)
            if not path.is_file() and info.get("relative_path"):
                path = artifact_path.parent / info["relative_path"]
            digest = sha256(path)
            if digest != info.get("sha256") or digest != previous.get("sha256"):
                raise ValueError(f"시뮬레이션이 현재 후보의 {role} SHA-256과 다릅니다. 다시 실행해 주세요.")
            if role == "threshold" and policy_current:
                dev = float(path.read_text(encoding="utf-8").strip())
                candidate = (comp.get("bundle_metadata") or {}).get("candidate") or {}
                if dev != candidate.get("operational_deploy_threshold_3sigma_cm") or dev != candidate.get("dev_file_threshold_cm"):
                    raise ValueError("시뮬레이션의 운영 DEV 소비값과 현재 Thres.forecast.DEV 값이 다릅니다.")
        receipt_path = folder / "receipt.json"
        receipt = read_json(receipt_path)
        if receipt.get("comparison_sha256") != comp_sha:
            raise ValueError("시뮬레이션 receipt와 comparison의 SHA-256 근거가 없거나 다릅니다.")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        reasons.append(str(exc))
    current = not reasons
    scope_reasons = []
    scope_evidence: dict = {"canonical_start_time": None, "canonical_end_time": None}
    try:
        canonical_start, canonical_end = _canonical_local_qc_span(
            str(comp.get("evaluated_snapshot_id") or ""), str(comp.get("scope") or "").upper())
        scope_evidence.update(canonical_start_time=str(canonical_start), canonical_end_time=str(canonical_end))
        actual_start = datetime.fromisoformat(str(comp.get("start_time") or ""))
        actual_end = datetime.fromisoformat(str(comp.get("end_time") or ""))
        if actual_start != canonical_start or actual_end != canonical_end:
            raise ValueError("시뮬레이션의 시작·종료 시각이 스냅샷 전체 평가 범위와 다릅니다. 부분 구간은 승격 근거로 사용할 수 없습니다.")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        scope_reasons.append("전체 평가 범위 검증 실패: " + str(exc))
    scope_current = not scope_reasons
    scope_evidence.update(passed=scope_current, reasons=scope_reasons)
    reasons.extend(scope_reasons)
    if reasons:
        verdict["promotion_allowed"] = False
        verdict["promotion_recommended"] = False
        verdict["reasons"] = list(dict.fromkeys(list(verdict.get("reasons") or []) + reasons))
        verdict["recommendation_reason"] = "승격 보류: " + " / ".join(verdict["reasons"])
        verdict["promotion_guardrails"] = {"passed": False, "reasons": verdict["reasons"]}
    verdict["bundle_current"] = current
    verdict["evaluation_scope_current"] = scope_current
    verdict["evaluation_scope_evidence"] = scope_evidence
    return {"policy_current": policy_current, "bundle_current": current,
            "evaluation_scope_current": scope_current, "evaluation_scope_evidence": scope_evidence,
            "evidence_status": ("historical_policy" if not policy_current else "stale_bundle" if not current
                                else "current" if scope_current else "scope_mismatch"),
            "local_qc_verdict": verdict}


def _candidate_qc_promotion_verdict(artifact: dict, comparison: dict | None,
                                    simulations: list[dict]) -> tuple[dict | None, dict]:
    """Use the exact active evaluation and current bundle; never fall back to another dataset."""
    comparison = comparison or {}
    snapshot_id = comparison.get("evaluated_snapshot_id") or artifact.get("snapshot_id")
    scope = str(comparison.get("evaluated_scope") or "TEST").upper()
    matching = [item for item in simulations if item.get("evaluated_snapshot_id") == snapshot_id
                and str(item.get("scope") or "").upper() == scope]
    selected = next((item for item in matching if item.get("policy_current") and item.get("bundle_current")
                     and item.get("evaluation_scope_current") is True),
                    matching[0] if matching else None)
    if selected is not None:
        verdict = dict(selected.get("local_qc_verdict") or {})
        if not (selected.get("policy_current") is True and selected.get("bundle_current") is True
                and selected.get("evaluation_scope_current") is True):
            message = "현재 정책·번들 해시와 전체 평가 범위가 일치하는 시뮬레이션이 필요합니다."
            verdict.update(promotion_allowed=False, promotion_recommended=False,
                           recommendation_reason=message)
            verdict["promotion_guardrails"] = {"passed": False, "reasons": [message]}
        verdict["local_qc_verdict"] = dict(selected.get("local_qc_verdict") or {})
        return selected, verdict
    missing = local_qc_promotion_verdict(None)
    diagnostic = honest_promotion_verdict(
        (comparison.get("models") or {}).get("candidate"), (comparison.get("models") or {}).get("champion_2025"),
        (comparison.get("anomaly_evaluation") or {}).get("natural_mqc_b_windows"))
    missing["recommendation_reason"] = ("현재 평가 스냅샷·범위와 같은 현재 번들의 로컬 QC 시뮬레이션이 없습니다. "
                                        + diagnostic["recommendation_reason"])
    missing["bundle_current"] = False
    missing["evaluation_scope_current"] = False
    return None, missing

def _summarize_local_qc_comparison(comp: dict, comp_sha: str, folder: Path) -> dict:
    evidence_status = _local_qc_evidence_status(comp, comp_sha, folder)
    verdict = evidence_status["local_qc_verdict"]
    t1_models = (comp.get("tier1") or {}).get("models") or {}
    t2_models = (comp.get("tier2") or {}).get("models") or {}
    t1_cand = t1_models.get("candidate") or {}
    t1_champ = t1_models.get("champion_2025") or {}
    t2_cand = t2_models.get("candidate") or {}
    t2_champ = t2_models.get("champion_2025") or {}
    c_online = (t2_cand.get("online") or {}).get("classification") or {}
    h_online = (t2_champ.get("online") or {}).get("classification") or {}
    c_cons = (t2_cand.get("consolidated") or {}).get("classification") or {}
    h_cons = (t2_champ.get("consolidated") or {}).get("classification") or {}
    c_cons_ev = (t2_cand.get("consolidated") or {}).get("events") or {}
    h_cons_ev = (t2_champ.get("consolidated") or {}).get("events") or {}
    return {
        "simulation_id": comp.get("simulation_id") or folder.name,
        "candidate_run_id": comp.get("candidate_run_id"),
        "station": comp.get("station"),
        "sensor": comp.get("sensor"),
        "evaluated_snapshot_id": comp.get("evaluated_snapshot_id"),
        "dataset_id": comp.get("dataset_id"),
        "scope": comp.get("scope"),
        "start_time": comp.get("start_time"),
        "end_time": comp.get("end_time"),
        "warmup_minutes": comp.get("warmup_minutes"),
        "comparison_sha256": comp_sha,
        "tier1_candidate_mae": t1_cand.get("mae"),
        "tier1_champion_mae": t1_champ.get("mae"),
        "online_candidate_fp": c_online.get("fp"),
        "online_candidate_fn": c_online.get("fn"),
        "online_champion_fp": h_online.get("fp"),
        "online_champion_fn": h_online.get("fn"),
        "consolidated_candidate_fp": c_cons.get("fp"),
        "consolidated_candidate_fn": c_cons.get("fn"),
        "consolidated_champion_fp": h_cons.get("fp"),
        "consolidated_champion_fn": h_cons.get("fn"),
        "consolidated_candidate_f1_100": c_cons.get("f1_score_100"),
        "consolidated_champion_f1_100": h_cons.get("f1_score_100"),
        "consolidated_candidate_event_recall_100": c_cons_ev.get("event_recall_100"),
        "consolidated_champion_event_recall_100": h_cons_ev.get("event_recall_100"),
        "labeled_b_count": c_cons.get("labeled_b_count"),
        "policy_version": comp.get("policy_version"),
        **evidence_status,
    }


def list_local_qc_simulations(candidate_run_id: str | None = None, sim_root: Path | None = None) -> list[dict]:
    root = _default_local_qc_root(sim_root)
    if not root.is_dir():
        return []
    summaries = []
    for comp_path in sorted(root.glob("*/comparison.json"), reverse=True):
        folder = comp_path.parent
        if folder.name == "development" or folder.name.startswith("SMOKE_"):
            continue
        try:
            comp_sha = sha256(comp_path)
            receipt_path = folder / "receipt.json"
            if receipt_path.is_file():
                receipt = read_json(receipt_path)
                if receipt.get("comparison_sha256") and receipt.get("comparison_sha256") != comp_sha:
                    continue
            comp = read_json(comp_path)
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(comp, dict) or comp.get("schema_version") != "local-qc-comparison-1":
            continue
        if candidate_run_id and comp.get("candidate_run_id") != candidate_run_id:
            continue
        summaries.append(_summarize_local_qc_comparison(comp, comp_sha, folder))
    summaries.sort(
        key=lambda item: (
            1 if item.get("policy_current") and item.get("bundle_current") and item.get("evaluation_scope_current") else 0,
            1 if str(item.get("scope") or "").upper() == "TEST" else 0,
            str(item.get("simulation_id") or ""),
        ),
        reverse=True,
    )
    return summaries


def get_local_qc_simulation(run_id: str, simulation_id: str | None = None, sim_root: Path | None = None) -> dict:
    root = _default_local_qc_root(sim_root)
    summaries = list_local_qc_simulations(candidate_run_id=run_id, sim_root=root)
    target_id = (simulation_id or "").strip() or (summaries[0]["simulation_id"] if summaries else "")
    if not target_id:
        return {
            "available": False,
            "candidate_run_id": run_id,
            "simulations": [],
            "message": "이 후보 모델에 대해 실행된 로컬 전체 QC 시뮬레이션이 없습니다.",
        }
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", target_id):
        raise ValueError("simulation_id 형식이 올바르지 않습니다.")
    folder = root / target_id
    comp_path = folder / "comparison.json"
    if not comp_path.is_file():
        raise ValueError(f"로컬 QC 시뮬레이션 비교 파일을 찾을 수 없습니다: {target_id}")
    comp_sha = sha256(comp_path)
    receipt_path = folder / "receipt.json"
    if receipt_path.is_file():
        receipt = read_json(receipt_path)
        if receipt.get("comparison_sha256") and receipt.get("comparison_sha256") != comp_sha:
            raise ValueError(f"시뮬레이션({target_id})의 receipt.json 해시와 comparison.json 해시가 일치하지 않습니다.")
    comp = read_json(comp_path)
    if comp.get("candidate_run_id") != run_id:
        raise ValueError("요청한 후보 모델과 시뮬레이션의 candidate_run_id가 다릅니다.")
    evidence_status = _local_qc_evidence_status(comp, comp_sha, folder)
    verdict = evidence_status["local_qc_verdict"]
    comp["historical_promotion_verdict"] = comp.get("promotion_verdict")
    comp["historical_promotion_allowed"] = comp.get("promotion_allowed")
    comp["promotion_verdict"] = verdict
    comp["promotion_allowed"] = verdict["promotion_allowed"]
    comp["local_qc_verdict"] = verdict
    comp["bundles"] = comp.get("bundle_metadata") or {}
    return {
        "available": True,
        "candidate_run_id": run_id,
        "simulation_id": target_id,
        "comparison_sha256": comp_sha,
        "local_qc_verdict": verdict,
        **evidence_status,
        "simulations": summaries,
        "comparison": comp,
    }


def get_local_qc_simulation_series(run_id: str, simulation_id: str | None = None, sim_root: Path | None = None) -> dict:
    root = _default_local_qc_root(sim_root)
    sim_info = get_local_qc_simulation(run_id=run_id, simulation_id=simulation_id, sim_root=root)
    if not sim_info.get("available"):
        return {"available": False, "message": sim_info.get("message", "시뮬레이션 시계열 파일이 없습니다.")}
    target_id = str(sim_info["simulation_id"])
    folder = root / target_id
    series_path = folder / "series.json"
    if not series_path.is_file():
        return {"available": False, "message": f"시뮬레이션({target_id})의 series.json 파일이 없습니다."}
    comp = sim_info["comparison"]
    expected_sha = ((comp.get("files") or {}).get("series") or {}).get("sha256")
    if expected_sha and sha256(series_path) != expected_sha:
        raise ValueError(f"시뮬레이션({target_id})의 series.json SHA-256 무결성 검증에 실패했습니다.")
    series = read_json(series_path)
    return {
        "available": True,
        "candidate_run_id": run_id,
        "simulation_id": target_id,
        **series,
    }


def run_local_qc_simulation_subprocess(
    run_id: str,
    *,
    snapshot_id: str | None = None,
    dataset_id: str | None = None,
    scope: str = "TEST",
    start_time: str | None = None,
    end_time: str | None = None,
    warmup_minutes: int = 180,
    simulation_id: str | None = None,
    single_inference: bool = False,
    tf_python: Path = TF_PYTHON,
    sim_root: Path | None = None,
    progress=None,
) -> dict:
    run_folder = CANDIDATE_RUNS_ROOT / run_id
    artifact_path = run_folder / "artifact.json"
    if not artifact_path.is_file():
        raise ValueError(f"후보 실행 기록을 찾을 수 없습니다: {run_id}")
    scope_clean = str(scope or "TEST").strip().upper()
    if scope_clean not in {"TEST", "ALL"}:
        raise ValueError("로컬 QC 시뮬레이션 scope는 TEST 또는 ALL이어야 합니다.")
    root = _default_local_qc_root(sim_root)
    root.mkdir(parents=True, exist_ok=True)
    sim_id = (simulation_id or "").strip() or (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + f"{run_id[-8:]}_{scope_clean}_" + uuid.uuid4().hex[:6]
    )
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", sim_id):
        raise ValueError("simulation_id 형식이 올바르지 않습니다.")
    simulator_script = BASE / "scripts/local_qc_simulator.py"
    command = [
        str(tf_python.resolve(strict=True)),
        "-X",
        "utf8",
        "-X",
        "faulthandler",
        str(simulator_script),
        "--candidate-run-id",
        run_id,
        "--scope",
        scope_clean,
        "--warmup-minutes",
        str(int(warmup_minutes)),
        "--output-root",
        str(root.resolve()),
        "--simulation-id",
        sim_id,
    ]
    if snapshot_id:
        command.extend(["--snapshot-id", str(snapshot_id).strip()])
    elif dataset_id:
        command.extend(["--dataset-id", str(dataset_id).strip()])
    if start_time and end_time:
        command.extend(["--start-time", str(start_time).strip(), "--end-time", str(end_time).strip()])
    if single_inference:
        command.append("--single-inference")

    def _emit(payload: dict) -> None:
        if callable(progress):
            try:
                progress(payload)
            except Exception:
                pass

    _emit({
        "stage": "local_qc_prepare",
        "stage_index": 1,
        "stage_total": 3,
        "percent": 10.0,
        "simulation_id": sim_id,
        "message": "로컬 QC 시뮬레이터 준비 및 원시 시계열 스트림 검증 중",
    })
    log_dir = root / sim_id
    stdout_lines: list[str] = []
    proc = subprocess.Popen(
        command,
        cwd=BASE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    try:
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            line = raw_line.strip()
            if not line:
                continue
            stdout_lines.append(line)
            if line.startswith("QC_START champion_2025"):
                _emit({
                    "stage": "local_qc_champion",
                    "stage_index": 1,
                    "stage_total": 3,
                    "percent": 20.0,
                    "simulation_id": sim_id,
                    "message": f"Champion 2025 전체 QC 재생 중 ({line})",
                })
            elif line.startswith("QC_DONE champion_2025"):
                _emit({
                    "stage": "local_qc_candidate",
                    "stage_index": 2,
                    "stage_total": 3,
                    "percent": 55.0,
                    "simulation_id": sim_id,
                    "message": "Champion 2025 재생 완료 · 신규 후보 모델 전체 QC 재생 시작",
                })
            elif line.startswith("QC_START candidate"):
                _emit({
                    "stage": "local_qc_candidate",
                    "stage_index": 2,
                    "stage_total": 3,
                    "percent": 60.0,
                    "simulation_id": sim_id,
                    "message": f"신규 후보 모델 전체 QC 재생 중 ({line})",
                })
            elif line.startswith("QC_DONE candidate"):
                _emit({
                    "stage": "local_qc_scoring",
                    "stage_index": 3,
                    "stage_total": 3,
                    "percent": 90.0,
                    "simulation_id": sim_id,
                    "message": "Tier 1 순수 예측 및 Tier 2 온라인·사후 최종 QC 채점 중",
                })
        _, stderr_text = proc.communicate(timeout=3600)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        raise RuntimeError(f"로컬 QC 시뮬레이션 시간 초과 ({sim_id})") from exc

    if proc.returncode != 0:
        err_tail = (stderr_text or "")[-2000:]
        raise RuntimeError(f"로컬 QC 시뮬레이션 실패 (코드 {proc.returncode}): {err_tail}")

    if log_dir.is_dir():
        (log_dir / "stdout.log").write_text("\n".join(stdout_lines) + "\n", encoding="utf-8")
        if stderr_text:
            (log_dir / "stderr.log").write_text(stderr_text, encoding="utf-8")

    _emit({
        "stage": "finished",
        "stage_index": 3,
        "stage_total": 3,
        "percent": 100.0,
        "simulation_id": sim_id,
        "message": "2-Tier 로컬 전체 QC 시뮬레이션 및 채점 완료",
    })
    return get_local_qc_simulation(run_id=run_id, simulation_id=sim_id, sim_root=root)


def list_candidate_runs(store: Path = STORE) -> list[dict]:
    items = []
    all_qc_sims = list_local_qc_simulations()
    qc_by_run: dict[str, list[dict]] = {}
    for sim_item in all_qc_sims:
        cid = str(sim_item.get("candidate_run_id") or "")
        if cid:
            qc_by_run.setdefault(cid, []).append(sim_item)
    for path in sorted(CANDIDATE_RUNS_ROOT.glob("*/artifact.json"), reverse=True):
        run_folder = path.parent
        if not re.fullmatch(r"\d{8}T\d{6}Z_[0-9a-f]{8}", run_folder.name):
            continue
        artifact = duel_series(read_json(path))
        if artifact.get("run_id") != run_folder.name:
            continue
        for role_info in (artifact.get("bundle") or {}).values():
            if isinstance(role_info, dict) and "path" in role_info:
                role_info["path"] = str(resolve_project_path(role_info["path"], BASE))
        comp_path = run_folder / "comparison.json"
        comparison = duel_comparison(read_json(comp_path)) if comp_path.is_file() else None
        run_qc_sims = qc_by_run.get(artifact["run_id"], [])
        primary_qc = None
        if isinstance(comparison, dict):
            primary_qc, verdict = _candidate_qc_promotion_verdict(artifact, comparison, run_qc_sims)
            comparison["candidate_vs_champion_2025"] = {
                **(comparison.get("candidate_vs_champion_2025") or {}), **verdict}
            npz_info = comparison.get("paired_predictions_npz")
            if isinstance(npz_info, dict) and "path" in npz_info:
                npz_info["path"] = str(resolve_project_path(npz_info["path"], BASE))
        elif run_qc_sims:
            primary_qc = run_qc_sims[0]
        aliases = get_model_aliases(artifact["station"], artifact["sensor"], store=store)["aliases"]
        items.append({
            "run_id": artifact["run_id"],
            "created_at": artifact["created_at"],
            "station": artifact["station"],
            "sensor": artifact["sensor"],
            "sea": artifact.get("sea"),
            "snapshot_id": artifact["snapshot_id"],
            **candidate_training_periods(artifact),
            "dataset_id": artifact["dataset_id"],
            "status": "FAILED" if artifact.get("worker_failure") or (run_folder / "worker_failure.json").is_file() else artifact["status"],
            "worker_failure": artifact.get("worker_failure"),
            "replay_verified": artifact.get("replay_verified", False),
            "threshold_sanity_passed": artifact.get("threshold_sanity_passed", False),
            "threshold": artifact.get("threshold"),
            "hyperparameters": artifact.get("hyperparameters"),
            "mlflow_registration": artifact.get("mlflow_registration"),
            "promotion": artifact.get("promotion"),
            "current_aliases": aliases,
            "cross_evaluations": artifact.get("cross_evaluations") or [],
            "active_evaluation": artifact.get("active_evaluation"),
            "local_qc_simulations": run_qc_sims,
            "local_qc_simulation": primary_qc,
            "comparison_sha256": sha256(comp_path) if comp_path.is_file() else artifact.get("comparison_sha256"),
            "comparison": comparison,
        })
    items.sort(key=lambda item: (str(item.get("created_at") or ""), item["run_id"]), reverse=True)
    return items[:30]
